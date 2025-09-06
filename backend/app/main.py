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

# Enable CORS so frontend (React) can connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
    Convert Windows path (C:\...) to Docker-friendly (/c/...) if needed.
    """
    if os.name == "nt":  # Windows
        drive = path.drive[0].lower()
        rest = str(path).replace("\\", "/").split(":", 1)[1]
        return f"/{drive}{rest}"
    return str(path)

@app.post("/run")
def run_code(request: CodeRequest):
    # Create isolated temp workspace
    run_id = str(uuid.uuid4())
    workdir = Path(tempfile.gettempdir()) / run_id
    workdir.mkdir(parents=True, exist_ok=True)

    try:
        # Decide filenames + commands per language
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

        # Write code + stdin files
        code_file = workdir / filename
        stdin_file = workdir / "stdin.txt"

        code_file.write_text(request.code)
        stdin_file.write_text(request.stdin)

        docker_path = to_docker_path(workdir)

        # Run in Docker container
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
        return {
            "stdout": "",
            "stderr": "Execution timed out",
            "exit_code": -1
        }

    finally:
        if workdir.exists():
            shutil.rmtree(workdir)
