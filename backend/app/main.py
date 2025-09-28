# backend_with_gemini.py
import os
import subprocess
import tempfile
import uuid
import shutil
from pathlib import Path
from typing import Optional
import json

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# === Google GenAI SDK ===
from google import genai
from google.genai import types

# Load environment variables
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize Gemini client
client = genai.Client(api_key=API_KEY)

# === FastAPI App ===
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Schemas ===
class CodeRequest(BaseModel):
    code: str
    stdin: str = ""
    language: str = "python"

class SuggestRequest(BaseModel):
    code: str
    stderr: Optional[str] = ""
    language: str = "python"

# === Error Database (JSON file) ===
ERROR_DB_FILE = Path("error_db.json")
if not ERROR_DB_FILE.exists():
    ERROR_DB_FILE.write_text(json.dumps({ "python": [], "c": [], "cpp": [], "java": [] }))

def load_error_db():
    return json.loads(ERROR_DB_FILE.read_text())

def save_error_db(db):
    ERROR_DB_FILE.write_text(json.dumps(db, indent=2))

# === Helper Functions ===
def is_nonsense_output(text: str) -> bool:
    bad_patterns = ["#include", "public class", "int main", "{", "}", ";"]
    return not text or text.strip() == "." or any(p in text for p in bad_patterns)

def extract_text(resp) -> str:
    if not resp:
        return ""
    if hasattr(resp, "text") and resp.text:
        return resp.text.strip()
    if hasattr(resp, "candidates") and resp.candidates:
        candidate = resp.candidates[0]
        content = getattr(candidate, "content", None)
        if content and hasattr(content, "parts") and content.parts:
            texts = [getattr(p, "text", "") for p in content.parts if getattr(p, "text", None)]
            return "".join(texts).strip()
    return ""

# === Fallback templates per language & error type ===
FALLBACK_TEMPLATES = {
    "python": {
        "SyntaxError": "SyntaxError detected: check parentheses, quotes, colons, and indentation.",
        "NameError": "NameError detected: variable or function not defined.",
        "ZeroDivisionError": "Division by zero detected.",
        "RecursionError": "RecursionError: maximum recursion depth exceeded.",
        "IndexError": "IndexError: list index out of range. Verify indices.",
        "KeyError": "KeyError: dictionary key not found. Ensure key exists."
    },
    "c": {
        "Segmentation fault": "Segmentation fault: invalid memory access. Check pointers/arrays.",
        "Floating point exception": "Floating point exception: invalid arithmetic operation.",
        "SyntaxError": "Syntax error: missing semicolon or brace."
    },
    "cpp": {
        "Segmentation fault": "Segmentation fault: invalid memory access. Check pointers/arrays.",
        "Floating point exception": "Floating point exception: invalid arithmetic operation.",
        "std::out_of_range": "std::out_of_range: accessing container with invalid index.",
        "SyntaxError": "Syntax error: missing semicolon or brace."
    },
    "java": {
        "ArithmeticException": "Division by zero detected.",
        "NullPointerException": "NullPointerException: accessing a null object reference.",
        "cannot find symbol": "Java cannot find symbol: variable, method, or class is undefined.",
        "ArrayIndexOutOfBoundsException": "Array index is out of bounds. Check array length.",
        "SyntaxError": "Syntax error: missing semicolon at end of statement."
    }
}

def fallback_suggestion(language: str, error: str) -> str:
    language = language.lower()
    for key, msg in FALLBACK_TEMPLATES.get(language, {}).items():
        if key.lower() in error.lower():
            return msg
    return "⚠️ No clear suggestion available."

def get_final_suggestion(language: str, error: str, ai_suggestion: str) -> str:
    if ai_suggestion and not is_nonsense_output(ai_suggestion):
        return ai_suggestion
    return fallback_suggestion(language, error)

# === Few-shot examples for prompt engineering ===
FEW_SHOT_EXAMPLES = {
    "python": [
        {
            "code": "prit('Hello')",
            "error": "NameError: name 'prit' is not defined",
            "explanation": "Typo in 'prit', should be 'print'.",
            "fixed_code": "print('Hello')"
        },
        {
            "code": "1/0",
            "error": "ZeroDivisionError: division by zero",
            "explanation": "Division by zero is not allowed.",
            "fixed_code": "1/1"
        },
    ],
    # Add similar examples for c, cpp, java
}

def build_prompt(language: str, code: str, error: str) -> str:
    examples = FEW_SHOT_EXAMPLES.get(language.lower(), [])
    prompt = f"You are an expert coding assistant. Analyze errors in {language} code.\n\n"
    for ex in examples:
        prompt += f"Code: {ex['code']}\nError: {ex['error']}\nExplanation: {ex['explanation']}\nCorrected Code: {ex['fixed_code']}\n\n"
    prompt += f"Now fix this code:\nCode: {code}\nError: {error}\n"
    prompt += "Explain the error in plain English and provide corrected code.\n"
    return prompt

# === Code Execution Endpoint ===
@app.post("/run")
def run_code(request: CodeRequest):
    run_id = str(uuid.uuid4())
    workdir = Path(tempfile.gettempdir()) / run_id
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        filename, image, run_cmd = None, None, None
        if request.language == "python":
            filename = "user_code.py"
            image = "code-runner-python"
            (workdir / filename).write_text(request.code)
            runner_code = """\
import sys, traceback
sys.setrecursionlimit(2000)
try:
    import user_code
except RecursionError:
    traceback.print_exc()
"""
            (workdir / "runner.py").write_text(runner_code)
            run_cmd = "PYTHONFAULTHANDLER=1 python -u runner.py < stdin.txt"
        elif request.language == "c":
            filename = "user_code.c"
            image = "code-runner-c"
            (workdir / filename).write_text(request.code)
            run_cmd = "gcc user_code.c -o user_code && ./user_code < stdin.txt"
        elif request.language in ("cpp", "c++"):
            filename = "user_code.cpp"
            image = "code-runner-cpp"
            (workdir / filename).write_text(request.code)
            run_cmd = "g++ user_code.cpp -o user_code && ./user_code < stdin.txt"
        elif request.language == "java":
            filename = "Main.java"
            image = "code-runner-java"
            (workdir / filename).write_text(request.code)
            run_cmd = "javac Main.java && java -cp . Main < stdin.txt"
        else:
            return {"error": f"Language {request.language} not supported"}
        (workdir / "stdin.txt").write_text(request.stdin or "")
        result = subprocess.run(
            ["docker", "run", "--rm", "-v", f"{str(workdir)}:/workspace", "-w", "/workspace",
             "--memory=256m", "--cpus=0.5", "--network", "none", image, "bash", "-c", run_cmd],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10
        )
        stderr_out = result.stderr.strip()
        exit_code = result.returncode
        if "Segmentation fault" in stderr_out:
            exit_code = 139
        elif "Floating point exception" in stderr_out:
            exit_code = 136
        elif "RecursionError" in stderr_out:
            exit_code = 1
        return {"stdout": result.stdout.strip(), "stderr": stderr_out, "exit_code": exit_code}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Execution timed out", "exit_code": -1}
    finally:
        if workdir.exists():
            shutil.rmtree(workdir)

# === Suggest Fix Endpoint (Updated: explanation-only feature) ===
@app.post("/suggest")
def suggest_fix(request: SuggestRequest):
    error = (request.stderr or "").strip()
    code = request.code
    language = request.language.lower()

    # Step 1: Lookup historical DB first
    db = load_error_db()
    for entry in db.get(language, []):
        if entry['error'].lower() == error.lower() and entry['code'].strip() == code.strip():
            return {"suggestion": entry['explanation']}  # explanation-only

    # Step 2: Build prompt + call Gemini
    prompt = build_prompt(language, code, error)
    suggestion = ""
    try:
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=256, temperature=0.25),
        )
        full_text = extract_text(resp)
        # Extract explanation-only if possible
        if "Explanation:" in full_text:
            suggestion = full_text.split("Explanation:")[1].strip()
        else:
            suggestion = full_text.strip()
    except Exception as e:
        suggestion = f"⚠️ Gemini API failed: {e}"

    final_suggestion = get_final_suggestion(language, error, suggestion)

    # Step 3: Save to DB if reasonable
    if final_suggestion and not is_nonsense_output(final_suggestion):
        db.setdefault(language, []).append({
            "code": code,
            "error": error,
            "explanation": final_suggestion,
            "fixed_code": code  # optional
        })
        save_error_db(db)

    return {"suggestion": final_suggestion}

# === Inline Suggest Fix Endpoint ===
@app.post("/suggest_inline")
def suggest_inline(request: SuggestRequest):
    error = (request.stderr or "").strip()
    code = request.code
    language = request.language.lower()

    # Step 1: Lookup historical DB first
    db = load_error_db()
    for entry in db.get(language, []):
        if entry['error'].lower() == error.lower() and entry['code'].strip() == code.strip():
            return {
                "explanation": entry['explanation'],
                "fixed_code": entry['fixed_code'],
                "explanation_only": entry['explanation']
            }

    # Step 2: Build prompt + call Gemini
    prompt = build_prompt(language, code, error) + "\nProvide corrected code inside triple backticks."
    try:
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=512, temperature=0.15),
        )
        result = extract_text(resp)
    except Exception as e:
        explanation = fallback_suggestion(language, error)
        return {
            "explanation": explanation,
            "fixed_code": code,
            "explanation_only": explanation
        }

    # Step 3: Parse Gemini output
    explanation, fixed_code = "", ""
    if "```" in result:
        parts = result.split("```")
        explanation = parts[0].replace("Explanation:", "").strip()
        code_block = parts[1].strip()
        # remove language tag if present
        if code_block.startswith(language):
            fixed_code_lines = code_block.split("\n")
            if fixed_code_lines[0].lower() == language:
                fixed_code_lines = fixed_code_lines[1:]
            fixed_code = "\n".join(fixed_code_lines).strip()
        else:
            fixed_code = code_block

        # Add comment to indicate this is the fixed line
        fixed_code = f"{fixed_code}  # ✅ Fixed by AI suggestion"
    else:
        explanation = result.strip()
        fixed_code = f"{code}  # ⚠️ No AI fix available, original code returned"

    # Step 4: Fallback if output is empty or nonsense
    if not explanation or is_nonsense_output(explanation):
        explanation = fallback_suggestion(language, error)
    if not fixed_code.strip():
        fixed_code = f"{code}  # ⚠️ No fix available, original code returned"

    # Step 5: Save to DB if reasonable and not duplicate
    db.setdefault(language, [])
    exists = any(
        entry['code'].strip() == code.strip() and entry['error'].strip() == error.strip()
        for entry in db[language]
    )
    if explanation and not is_nonsense_output(explanation) and not exists:
        db[language].append({
            "code": code,
            "error": error,
            "explanation": explanation,
            "fixed_code": fixed_code
        })
        save_error_db(db)

    return {
        "explanation": explanation,
        "fixed_code": fixed_code,
        "explanation_only": explanation
    }

