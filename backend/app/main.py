# backend_with_gemini.py
import os, subprocess, tempfile, uuid, shutil, re, json
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# === Google GenAI SDK ===
from google import genai
from google.genai import types

# === Language Detection ===
from pygments.lexers import guess_lexer
from pygments.util import ClassNotFound

# === SQLAlchemy for DB ===
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import sessionmaker, declarative_base, Session


# ==============================
# ENV + INIT
# ==============================
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================
# Database Setup
# ==============================
DATABASE_URL = "sqlite:///./code_runner.db"  # Local SQLite DB

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class CodeHistory(Base):
    __tablename__ = "code_history"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(Text)
    language = Column(String(20))
    stdout = Column(Text)
    stderr = Column(Text)
    ai_explanation = Column(Text)
    ai_fixed_code = Column(Text)

Base.metadata.create_all(bind=engine)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==============================
# Schemas
# ==============================
class CodeRequest(BaseModel):
    code: str
    stdin: str = ""
    language: str = "python"

class SuggestRequest(BaseModel):
    code: str
    stderr: Optional[str] = ""
    language: str = "python"

class DetectRequest(BaseModel):
    code: str
    auto_loaded: bool = False

class SaveCodeRequest(BaseModel):
    code: str
    language: str
    stdout: str = ""
    stderr: str = ""
    ai_explanation: Optional[str] = ""
    ai_fixed_code: Optional[str] = ""

# ==============================
# Error Database
# ==============================
ERROR_DB_FILE = Path("error_db.json")
if not ERROR_DB_FILE.exists():
    ERROR_DB_FILE.write_text(json.dumps({ "python": [], "c": [], "cpp": [], "java": [] }))

def load_error_db():
    return json.loads(ERROR_DB_FILE.read_text())

def save_error_db(db):
    ERROR_DB_FILE.write_text(json.dumps(db, indent=2))

# ==============================
# Helpers
# ==============================
def is_nonsense_output(text: str) -> bool:
    return not text or text.strip() in [".", ""]

def extract_text(resp) -> str:
    """Extracts plain text from Gemini response object"""
    if hasattr(resp, "text") and resp.text:
        return resp.text.strip()
    if hasattr(resp, "candidates") and resp.candidates:
        cand = resp.candidates[0]
        if hasattr(cand, "content") and hasattr(cand.content, "parts"):
            texts = [getattr(p, "text", "") for p in cand.content.parts if getattr(p, "text", None)]
            return "".join(texts).strip()
    return ""

def clean_code_block(text: str, language: str) -> str:
    """Strip markdown, triple backticks, and leading language labels"""
    if not text:
        return ""
    code = text.strip()
    if "```" in code:
        parts = code.split("```")
        # take the last fenced block
        for part in reversed(parts):
            if part.strip():
                code = part.strip()
                break
    if code.lower().startswith(language):
        code = "\n".join(code.splitlines()[1:])
    return code.strip()

# ==============================
# Templates + Few-shot examples
# ==============================
LANGUAGE_TEMPLATES = {
    "python": "print('Hello, World!')\n",
    "c": "#include <stdio.h>\nint main(){\n    printf(\"Hello, World!\\n\");\n    return 0;\n}\n",
    "cpp": "#include <iostream>\nusing namespace std;\nint main(){\n    cout << \"Hello, World!\" << endl;\n    return 0;\n}\n",
    "java": "public class Main {\n    public static void main(String[] args){\n        System.out.println(\"Hello, World!\");\n    }\n}\n"
}

# Few-shot examples for better AI consistency
FEW_SHOT_EXAMPLES = {
    "python": [
        {
            "code": "prit('Hello')",
            "error": "NameError: name 'prit' is not defined",
            "explanation": "You misspelled 'print'.",
            "fixed_code": "print('Hello')"
        },
        {
            "code": "print('Hello'",
            "error": "SyntaxError: unexpected EOF while parsing",
            "explanation": "Python expected a closing parenthesis or quote.",
            "fixed_code": "print('Hello')"
        }
    ]
}

def fallback_suggestion(language: str, error: str) -> str:
    """Fallback generic explanations"""
    if "syntax" in error.lower():
        return "Your code has a syntax error. Check for missing brackets, quotes, or colons."
    if "nameerror" in error.lower():
        return "You are using a variable or function that is not defined."
    if "typeerror" in error.lower():
        return "A function or operator is being used with the wrong data type."
    if "runtime" in error.lower():
        return "The program crashed during execution. Review the error details."
    return f"An error occurred in your {language} code: {error}"

# ==============================
# Prompt Builder + Suggestion Normalizer
# ==============================
def build_prompt(language: str, code: str, error: str) -> str:
    lang = language.lower()
    examples = FEW_SHOT_EXAMPLES.get(lang, [])

    prompt_lines = [
        f"You are an expert {language} coding assistant.",
        "",
        "Given the user's CODE and the ERROR message, return two things:",
        "1) explanation — a short, clear explanation of the error (1-3 sentences).",
        "2) fixed_code — the corrected full source code.",
        "",
        "IMPORTANT: Prefer JSON output:",
        '{ "explanation": "...", "fixed_code": "..." }',
        "",
        "If you cannot, then return two labeled sections:",
        "Explanation:",
        "Fixed Code:",
        "",
        "Examples:"
    ]

    for ex in examples[:2]:
        example_json = json.dumps({
            "explanation": ex["explanation"],
            "fixed_code": ex["fixed_code"]
        }, ensure_ascii=False)
        prompt_lines += [
            "Input Code:",
            ex["code"],
            "Error:",
            ex["error"],
            "Expected Output (JSON):",
            example_json,
            ""
        ]

    prompt_lines += [
        "Now fix this code:",
        "Input Code:",
        code,
        "Error:",
        error
    ]
    return "\n".join(prompt_lines)


def get_final_suggestion(language: str, error: str, ai_suggestion) -> str:
    def strip_code_fences(text: str) -> str:
        if not text:
            return ""
        t = text.strip()
        t = re.sub(r"^```[\w+\-]*\n", "", t)
        t = re.sub(r"\n```$", "", t)
        return t.strip()

    if isinstance(ai_suggestion, dict):
        expl = ai_suggestion.get("explanation") or ai_suggestion.get("suggestion")
        if expl and not is_nonsense_output(expl):
            return str(expl).strip()

    if isinstance(ai_suggestion, str):
        s = strip_code_fences(ai_suggestion)
        try:
            parsed = json.loads(s)
            if isinstance(parsed, dict) and "explanation" in parsed:
                return parsed["explanation"].strip()
        except Exception:
            pass
        if "Explanation:" in s:
            try:
                return s.split("Explanation:")[1].split("Fixed Code:")[0].strip()
            except Exception:
                pass
        if s and not is_nonsense_output(s):
            return s

    return fallback_suggestion(language, error)

# ==============================
# Language Detection
# ==============================
def detect_language_from_code(code: str) -> str:
    try:
        lexer = guess_lexer(code)
        name = lexer.name.lower()
        if "python" in name: return "python"
        if "c++" in name: return "cpp"
        if name == "c": return "c"
        if "java" in name: return "java"
    except ClassNotFound:
        pass
    if "#include" in code: return "cpp" if "iostream" in code else "c"
    if "System.out.println" in code: return "java"
    return "python"

@app.post("/detect_language")
def detect_language(request: DetectRequest):
    code = (request.code or "").strip()
    detected = detect_language_from_code(code) if code else "python"
    load_template = not code or request.auto_loaded
    return {
        "language": detected,
        "load_template": load_template,
        "template": LANGUAGE_TEMPLATES.get(detected, "") if load_template else ""
    }

# ==============================
# Code Execution
# ==============================
@app.post("/run")
def run_code(request: CodeRequest):
    run_id = str(uuid.uuid4())
    workdir = Path(tempfile.gettempdir()) / run_id
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        if request.language == "python":
            (workdir / "user_code.py").write_text(request.code)
            (workdir / "stdin.txt").write_text(request.stdin or "")
            run_cmd = "python3 user_code.py < stdin.txt"
            image = "code-runner-python"
        elif request.language == "c":
            (workdir / "user_code.c").write_text(request.code)
            (workdir / "stdin.txt").write_text(request.stdin or "")
            run_cmd = "gcc user_code.c -o user_code && ./user_code < stdin.txt"
            image = "code-runner-c"
        elif request.language == "cpp":
            (workdir / "user_code.cpp").write_text(request.code)
            (workdir / "stdin.txt").write_text(request.stdin or "")
            run_cmd = "g++ user_code.cpp -o user_code && ./user_code < stdin.txt"
            image = "code-runner-cpp"
        elif request.language == "java":
            (workdir / "Main.java").write_text(request.code)
            (workdir / "stdin.txt").write_text(request.stdin or "")
            run_cmd = "javac Main.java && java Main < stdin.txt"
            image = "code-runner-java"
        else:
            return {"error": "Unsupported language"}

        result = subprocess.run(
            ["docker","run","--rm","-v",f"{str(workdir)}:/workspace","-w","/workspace",
             "--network","none","--memory","256m","--cpus","0.5",image,"bash","-c",run_cmd],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10
        )
        return {"stdout": result.stdout.strip(),"stderr": result.stderr.strip(),"exit_code": result.returncode}
    except subprocess.TimeoutExpired:
        return {"stdout":"","stderr":"Execution timed out","exit_code":-1}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

# ==============================
# Save Code to DB
# ==============================
@app.post("/save_code")
def save_code(request: SaveCodeRequest, db: Session = Depends(get_db)):
    entry = CodeHistory(
        code=request.code,
        language=request.language,
        stdout=request.stdout,
        stderr=request.stderr,
        ai_explanation=request.ai_explanation or "",
        ai_fixed_code=request.ai_fixed_code or ""
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"message": "Code saved successfully", "id": entry.id}

# ==============================
# Load Previous Codes
# ==============================
@app.get("/history")
def load_history(language: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(CodeHistory)
    if language:
        query = query.filter(CodeHistory.language == language)
    entries = query.order_by(CodeHistory.id.desc()).limit(50).all()
    return [
        {
            "id": e.id,
            "code": e.code,
            "language": e.language,
            "stdout": e.stdout,
            "stderr": e.stderr,
            "ai_explanation": e.ai_explanation,
            "ai_fixed_code": e.ai_fixed_code
        } for e in entries
    ]

# ==============================
# Suggest Fix
# ==============================
@app.post("/suggest")
def suggest_fix(request: SuggestRequest):
    error = (request.stderr or "").strip()
    code = request.code
    language = request.language.lower()

    db = load_error_db()
    for entry in db.get(language, []):
        if entry['error'].lower() == error.lower() and entry['code'].strip() == code.strip():
            return {"suggestion": entry['explanation']}

    prompt = build_prompt(language, code, error)
    suggestion = ""
    try:
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=256, temperature=0.25),
        )
        full_text = extract_text(resp)
        if "Explanation:" in full_text:
            suggestion = full_text.split("Explanation:")[1].split("Fixed Code:")[0].strip()
        else:
            suggestion = full_text.strip()
    except Exception as e:
        suggestion = f"⚠️ Gemini API failed: {e}"

    final_suggestion = get_final_suggestion(language, error, suggestion)
    if final_suggestion and not is_nonsense_output(final_suggestion):
        db.setdefault(language, []).append({
            "code": code,"error": error,
            "explanation": final_suggestion,"fixed_code": code
        })
        save_error_db(db)
    return {"suggestion": final_suggestion}

# ==============================
# Suggest Inline (Explanation + Fix)
# ==============================
@app.post("/suggest_inline")
def suggest_inline(request: SuggestRequest):
    code = request.code.strip()
    error = (request.stderr or "").strip()
    language = request.language.lower()

    db = load_error_db()
    for entry in db.get(language, []):
        if entry["error"].lower() == error.lower() and entry["code"].strip() == code:
            return {"explanation": entry["explanation"],"fixed_code": entry["fixed_code"]}

    prompt = f"""
Return JSON only. Keys: explanation, fixed_code.
Code ({language}):
{code}

Error:
{error}
"""
    try:
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=400,temperature=0.2),
        )
        raw = extract_text(resp)
    except Exception as e:
        return {"explanation": f"AI unavailable: {e}","fixed_code": code + "  # ⚠️ No fix"}

    explanation, fixed_code = "", ""
    try:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            parsed = json.loads(match.group(0))
            explanation = parsed.get("explanation","").strip()
            fixed_code = clean_code_block(parsed.get("fixed_code",""), language)
        else:
            explanation = raw
            fixed_code = code
    except Exception:
        explanation = raw
        fixed_code = code

    if not fixed_code or fixed_code.strip() == code.strip():
        fixed_code = code + ("\n# ✅ Fixed suggestion" if language=="python" else "\n// ✅ Fixed suggestion")

    if explanation and not is_nonsense_output(explanation):
        db.setdefault(language, []).append({
            "code": code,"error": error,
            "explanation": explanation,"fixed_code": fixed_code
        })
        save_error_db(db)

    return {"explanation": explanation,"fixed_code": fixed_code}
