import subprocess
import sys

def main():
    code_file = "/workspace/user_code.py"
    stdin_file = "/workspace/stdin.txt"

    try:
        with open(stdin_file, "r") as f:
            stdin_data = f.read()

        process = subprocess.Popen(
            ["python", code_file],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        stdout, stderr = process.communicate(input=stdin_data, timeout=5)

        if stdout:
            print(stdout, end="")
        if stderr:
            print(stderr, end="", file=sys.stderr)

        sys.exit(process.returncode)

    except subprocess.TimeoutExpired:
        print("Execution timed out", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
