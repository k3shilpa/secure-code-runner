import subprocess
import tempfile
import os
import uuid
import shutil
from pathlib import Path
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow frontend to talk to backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CodeRequest(BaseModel):
    code: str
    stdin: str = ""
    language: str = "python"

def to_docker_path(path: Path) -> str:
    """
    Convert Windows path (C:\...) to Docker-friendly (/c/...) if needed
    """
    if os.name == "nt":  # Windows
        drive = path.drive[0].lower()
        rest = str(path).replace("\\", "/").split(":", 1)[1]
        return f"/{drive}{rest}"
    return str(path)

@app.post("/run")
def run_code(request: CodeRequest):
    if request.language != "python":
        return {"error": "Only Python supported in MVP"}

    # Unique work directory
    run_id = str(uuid.uuid4())
    workdir = Path(tempfile.gettempdir()) / run_id
    workdir.mkdir(parents=True, exist_ok=True)

    code_file = workdir / "user_code.py"
    stdin_file = workdir / "stdin.txt"

    # Always create both files
    code_file.write_text(request.code.replace("input(", "input() #"))
    stdin_file.write_text(request.stdin or "")   # ✅ ensures stdin.txt always exists

    try:
        docker_path = to_docker_path(workdir)

        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "-v", f"{docker_path}:/workspace",   # mount temp folder into /workspace
                "--memory=128m", "--cpus=0.5", "--network", "none",
                "code-runner-python"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode
        }

    except subprocess.TimeoutExpired:
        return {"error": "Execution timed out"}
    finally:
        if workdir.exists():
            shutil.rmtree(workdir)
