import subprocess
import tempfile
import os
import uuid
import shutil
from pathlib import Path
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

# === AI Model (Flan-T5 for explanations) ===
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

MODEL_NAME = "google/flan-t5-small"  # lightweight model
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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

# === RUN ENDPOINT ===
@app.post("/run")
def run_code(request: CodeRequest):
    run_id = str(uuid.uuid4())
    workdir = Path(tempfile.gettempdir()) / run_id
    workdir.mkdir(parents=True, exist_ok=True)

    try:
        # Language setup
        if request.language == "python":
            filename = "user_code.py"
            image = "code-runner-python"
            run_cmd = "python user_code.py < stdin.txt"

        elif request.language == "c":
            filename = "user_code.c"
            image = "code-runner-c"
            run_cmd = "gcc user_code.c -o user_code && ./user_code < stdin.txt"

        elif request.language == "cpp":
            filename = "user_code.cpp"
            image = "code-runner-cpp"
            run_cmd = "g++ user_code.cpp -o user_code && ./user_code < stdin.txt"

        elif request.language == "java":
            filename = "Main.java"
            image = "code-runner-java"
            run_cmd = "javac Main.java && java Main < stdin.txt"

        else:
            return {"error": f"Language {request.language} not supported"}

        # Write code + stdin
        (workdir / filename).write_text(request.code)
        (workdir / "stdin.txt").write_text(request.stdin)

        docker_path = str(workdir)

        # Run inside Docker
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "-v", f"{docker_path}:/workspace",
                "--memory=256m", "--cpus=0.5", "--network", "none",
                image,
                "bash", "-c", run_cmd
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )

        return {
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "exit_code": result.returncode
        }

    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Execution timed out", "exit_code": -1}

    finally:
        if workdir.exists():
            shutil.rmtree(workdir)


# === HELPER: Detect nonsense output ===
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
    error = request.stderr or ""
    code = request.code

    prompt = f"""
The following {request.language} code has an error.

Code:
{code}

Error:
{error}

Explain the error in simple terms and suggest a fix.
"""

    inputs = tokenizer(prompt, return_tensors="pt", truncation=True)
    outputs = model.generate(**inputs, max_new_tokens=256, num_beams=4)
    suggestion = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()

    # === Fallback rules ===
    if is_nonsense_output(suggestion):
        if "SyntaxError" in error:
            suggestion = "🛠 Fix: Missing parenthesis, colon, or indentation."
        elif "NameError" in error:
            suggestion = "🛠 Fix: You're using a variable that isn't defined."
        elif "ZeroDivisionError" in error:
            suggestion = "🛠 Fix: You're dividing by zero."
        elif "IndentationError" in error:
            suggestion = "🛠 Fix: Your code indentation is incorrect."
        elif "expected ‘;’" in error or "missing ';'" in error:
            suggestion = "🛠 Fix: Missing semicolon at end of statement."
        elif "cannot find symbol" in error:
            suggestion = "🛠 Fix: You are using an undefined variable or method in Java."
        else:
            suggestion = "⚠️ No clear AI suggestion available."

    return {"suggestion": suggestion}


# === INLINE FIX ENDPOINT ===
@app.post("/suggest_inline")
def suggest_inline(request: SuggestRequest):
    error = request.stderr or ""
    code = request.code

    prompt = f"""
The following {request.language} code has an error.

Code:
{code}

Error:
{error}

Task:
1. Explain the error briefly.
2. Provide the corrected code inside triple backticks.
"""

    inputs = tokenizer(prompt, return_tensors="pt", truncation=True)
    outputs = model.generate(**inputs, max_new_tokens=256, num_beams=4)
    result = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()

    explanation, fixed_code = result, ""

    if "```" in result:
        parts = result.split("```")
        explanation = parts[0].strip()
        fixed_code = parts[1].replace("python", "").replace("cpp", "").replace("java", "").strip()

    # === Fallback rules ===
    if is_nonsense_output(explanation):
        if "SyntaxError" in error:
            explanation = "You have a SyntaxError. Likely missing a parenthesis or colon."
            # auto-fix unbalanced parentheses
            open_paren, close_paren = code.count("("), code.count(")")
            if open_paren > close_paren:
                fixed_code = code + (")" * (open_paren - close_paren))
        elif "NameError" in error:
            explanation = "You used a variable/function that is not defined."
        elif "IndentationError" in error:
            explanation = "Your indentation is wrong. Align your code properly."
        elif "ZeroDivisionError" in error:
            explanation = "You divided by zero. Add a check before dividing."
        elif "expected ‘;’" in error or "missing ';'" in error:
            explanation = "C/C++ error: missing semicolon at the end of a statement."
            fixed_code = code.replace("\n  return", ";\n  return")
        elif "cannot find symbol" in error:
            explanation = "Java error: variable/method not defined. Declare it before using."
        elif "cannot find symbol" in error:
            explanation = "Java error: variable 'x' is not defined. Added a declaration for it."
            if "System.out.println(x);" in code:
                fixed_code = code.replace(
            "System.out.println(x);",
            "int x = 0;\n    System.out.println(x);"
            )

        else:
            explanation = "⚠️ No clear AI explanation available."

    if fixed_code == "":
        fixed_code = code  # fallback if no change

    return {"explanation": explanation, "fixed_code": fixed_code}
