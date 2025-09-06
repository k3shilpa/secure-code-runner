from fastapi import FastAPI
from pydantic import BaseModel
import subprocess
import tempfile

app = FastAPI()

class CodeRequest(BaseModel):
    code: str
    stdin: str = ""
    language: str = "python"

@app.post("/run")
def run_code(request: CodeRequest):
    if request.language != "python":
        return {"error": "Only Python supported in MVP"}

    try:
        # Modify user code to remove prompts from input()
        safe_code = request.code.replace("input(", "input() #")

        # Create a temporary Python file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".py") as tmp:
            tmp.write(safe_code.encode())
            tmp_path = tmp.name

        # Run code with subprocess
        process = subprocess.Popen(
            ["python", tmp_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(input=request.stdin, timeout=5)

        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": process.returncode
        }
    except subprocess.TimeoutExpired:
        return {"error": "Execution timed out"}
    except Exception as e:
        return {"error": str(e)}
