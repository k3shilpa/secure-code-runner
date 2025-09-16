import subprocess
import tempfile
import uuid
import shutil
from pathlib import Path
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

# === AI Model: CodeT5-base (code-specific model, runs on CPU) ===
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

MODEL_NAME = "Salesforce/codet5-base"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)

# === FastAPI App ===
app = FastAPI()

# Enable CORS so frontend (React) can access backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Request Schemas ===
class CodeRequest(BaseModel):
    code: str
    stdin: str = ""
    language: str = "python"

class SuggestRequest(BaseModel):
    code: str
    stderr: Optional[str] = ""
    language: str = "python"

# === RUN CODE ENDPOINT ===
@app.post("/run")
def run_code(request: CodeRequest):
    """
    Runs user code inside a Docker container for isolation.
    Supports Python, C, C++, and Java.
    """
    run_id = str(uuid.uuid4())
    workdir = Path(tempfile.gettempdir()) / run_id
    workdir.mkdir(parents=True, exist_ok=True)

    try:
        filename = None
        image = None
        run_cmd = None

        if request.language == "python":
            filename = "user_code.py"
            image = "code-runner-python"

            # Write user code
            (workdir / filename).write_text(request.code)

            # Runner script (forces RecursionError instead of silent crash)
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

        elif request.language == "cpp":
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

        # Always write stdin
        (workdir / "stdin.txt").write_text(request.stdin)

        docker_path = str(workdir)

        # Run inside Docker
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "-v", f"{docker_path}:/workspace",
                "-w", "/workspace",
                "--memory=256m", "--cpus=0.5", "--network", "none",
                image,
                "bash", "-c", run_cmd
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )

        stderr_out = result.stderr.strip()
        exit_code = result.returncode

        # Normalize signals
        if "Segmentation fault" in stderr_out:
            exit_code = 139
        elif "Floating point exception" in stderr_out:
            exit_code = 136
        elif "RecursionError" in stderr_out:
            exit_code = 1

        return {
            "stdout": result.stdout.strip(),
            "stderr": stderr_out,
            "exit_code": exit_code
        }

    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Execution timed out", "exit_code": -1}

    finally:
        if workdir.exists():
            shutil.rmtree(workdir)

# === HELPER: Detect useless AI output ===
def is_nonsense_output(text: str) -> bool:
    bad_patterns = ["#include", "public class", "int main", "{", "}", ";"]
    return (
        text.strip() == ""
        or text.strip() == "."
        or any(p in text for p in bad_patterns)
    )

# === SUGGEST ENDPOINT ===
@app.post("/suggest")
def suggest_fix(request: SuggestRequest):
    """
    Explains errors in simple terms and suggests fixes.
    Uses CodeT5 for reasoning + fallback rules if model fails.
    """
    error = request.stderr or ""
    code = request.code

    prompt = f"""
The following {request.language} code has an error.

Code:
{code}

Error:
{error}

Task:
Explain the error in simple terms and suggest how to fix it.
"""

    try:
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True)
        outputs = model.generate(
            **inputs,
            max_new_tokens=128,
            num_beams=2,
            early_stopping=True
        )
        suggestion = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
    except Exception:
        suggestion = ""

    # Fallback rules
    if is_nonsense_output(suggestion):
        if "SyntaxError" in error or "EOF while parsing" in error:
            suggestion = "🛠 Fix: SyntaxError → something is not closed (quote, parenthesis, etc.)."
        elif "NameError" in error:
            suggestion = "🛠 Fix: You’re using a variable or function that isn’t defined."
        elif "ZeroDivisionError" in error:
            suggestion = "🛠 Fix: Division by zero. Add a check before division."
        elif "IndentationError" in error:
            suggestion = "🛠 Fix: Indentation is incorrect. Align code properly."
        elif "expected" in error or "missing ';'" in error:
            suggestion = "🛠 Fix: Missing semicolon at end of statement in C/C++."
        elif "cannot find symbol" in error and request.language == "java":
            suggestion = "🛠 Fix: Undefined variable/method in Java. Declare it before use."
        else:
            suggestion = "⚠️ No clear AI suggestion available."

    return {"suggestion": suggestion}

# === INLINE FIX ENDPOINT ===
# === INLINE FIX ENDPOINT ===
@app.post("/suggest_inline")
def suggest_inline(request: SuggestRequest):
    """
    Provides both an explanation AND corrected code.
    If AI output is nonsense, fallback rules ensure valid output.
    """
    error = request.stderr or ""
    code = request.code
    language = request.language.lower()

    prompt = f"""
You are a coding assistant. The following {language} code has an error.

Code:
{code}

Error:
{error}

Task:
1. Explain the error clearly in plain English.
2. Provide the corrected code inside triple backticks with the correct language tag.

Example:
Explanation: The error means ...
```{language}
<fixed code here>
"""
    try:
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True)
        outputs = model.generate(
        **inputs,
        max_new_tokens=128,
        num_beams=2,
        early_stopping=True
        )
        result = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
    except Exception:
        return {"explanation": "⚠️ AI model failed", "fixed_code": code}
    explanation, fixed_code = "", ""

# === Parse AI Output ===
    if "```" in result:
        parts = result.split("```")
        explanation = parts[0].replace("Explanation:", "").strip()
    # remove language tag if present
        fixed_code = parts[1].replace(language, "").strip()
    else:
        explanation = result.strip()

# === Fallback Handling for nonsense ===
    if is_nonsense_output(explanation) or not explanation:
        if "SyntaxError" in error:
            explanation = "You have a SyntaxError. Likely missing a parenthesis, bracket, or quote."
        if code.count("(") > code.count(")"):
            fixed_code = code + ")"
        else:
            fixed_code = code
    elif "NameError" in error:
        explanation = "You used a variable or function that is not defined."
        fixed_code = code  # cannot auto-fix without context
    elif "IndentationError" in error:
        explanation = "Your indentation is incorrect. Align code blocks consistently."
        fixed_code = code
    elif "ZeroDivisionError" in error:
        explanation = "You are dividing by zero. Add a check before dividing."
        fixed_code = code
    elif ("expected" in error or "missing ';'" in error) and language in ["c", "cpp", "c++"]:
        explanation = "C/C++ error: missing semicolon."
        # Try to insert missing semicolon before return
        fixed_code = code.replace("return", ";\n  return") if "return" in code else code + ";"
    elif "cannot find symbol" in error and language == "java":
        explanation = "Java error: variable/method not defined. Declare it before using."
        if "System.out.println(x);" in code:
            fixed_code = code.replace(
                "System.out.println(x);",
                "int x = 0;\n        System.out.println(x);"
            )
        else:
            fixed_code = code
    else:
        explanation = "⚠️ No clear AI explanation available."
        fixed_code = code

# If fixed_code is empty, just return original code
    if not fixed_code.strip():
        fixed_code = code

    return {"explanation": explanation, "fixed_code": fixed_code}
