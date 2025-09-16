import requests

BASE_URL = "http://127.0.0.1:8000"

def run_test(name, data, endpoint="/run", expect_stdout=None, expect_stderr=None, expect_exit=None):
    """Helper to run a test case and print PASS/FAIL."""
    try:
        r = requests.post(f"{BASE_URL}{endpoint}", json=data, timeout=30)
        result = r.json()
    except Exception as e:
        print(f"❌ {name} - Request failed: {e}")
        return

    # Check conditions
    passed = True
    if expect_stdout is not None and expect_stdout not in result.get("stdout", ""):
        passed = False
    if expect_stderr is not None and expect_stderr not in result.get("stderr", ""):
        passed = False
    if expect_exit is not None and result.get("exit_code") != expect_exit:
        passed = False

    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} - {name}")
    print("   Response:", result)


# === PYTHON TESTS ===
def test_python():
    run_test("Python Success", {"code": "print('Hello, World!')", "stdin": "", "language": "python"}, expect_stdout="Hello, World!", expect_exit=0)
    run_test("Python ZeroDivisionError", {"code": "print(1/0)", "stdin": "", "language": "python"}, expect_stderr="ZeroDivisionError", expect_exit=1)
    run_test("Python Syntax Error", {"code": "print('Hello'", "stdin": "", "language": "python"}, expect_stderr="SyntaxError", expect_exit=1)
    run_test("Python With stdin", {"code": "name=input();print('Hi',name)", "stdin": "Alice", "language": "python"}, expect_stdout="Hi Alice", expect_exit=0)
    run_test("Python Infinite Recursion", {"code": "def f(): return f(); f()", "stdin": "", "language": "python"}, expect_stderr="RecursionError", expect_exit=1)


# === C TESTS ===
def test_c():
    run_test("C Success", {"code": '#include <stdio.h>\nint main(){printf("Hi\\n");return 0;}', "stdin": "", "language": "c"}, expect_stdout="Hi", expect_exit=0)
    run_test("C Missing Semicolon", {"code": '#include <stdio.h>\nint main(){printf("Hi") return 0;}', "stdin": "", "language": "c"}, expect_stderr="expected", expect_exit=1)
    run_test("C Segmentation Fault", {"code": '#include <stdio.h>\nint main(){ int *p=NULL; *p=5; return 0; }', "stdin": "", "language": "c"}, expect_exit=139)  # 139 = segfault


# === C++ TESTS ===
def test_cpp():
    run_test("C++ Success", {"code": '#include <iostream>\nusing namespace std;\nint main(){cout << "Hi" << endl;return 0;}', "stdin": "", "language": "cpp"}, expect_stdout="Hi", expect_exit=0)
    run_test("C++ Syntax Error", {"code": '#include <iostream>\nusing namespace std;\nint main(){cout << "Hi" return 0;}', "stdin": "", "language": "cpp"}, expect_stderr="error", expect_exit=1)
    run_test("C++ Divide by Zero", {"code": '#include <iostream>\nusing namespace std;\nint main(){int x=0;cout<<10/x;return 0;}', "stdin": "", "language": "cpp"}, expect_exit=136)  # SIGFPE


# === JAVA TESTS ===
def test_java():
    run_test("Java Success", {"code": 'public class Main { public static void main(String[] args){ System.out.println("Hi"); } }', "stdin": "", "language": "java"}, expect_stdout="Hi", expect_exit=0)
    run_test("Java Undefined Variable", {"code": 'public class Main { public static void main(String[] args){ System.out.println(x); } }', "stdin": "", "language": "java"}, expect_stderr="cannot find symbol", expect_exit=1)
    run_test("Java Divide by Zero", {"code": 'public class Main { public static void main(String[] args){ int x=5/0; } }', "stdin": "", "language": "java"}, expect_stderr="Exception", expect_exit=1)


# === AI SUGGEST TESTS ===
def test_ai_suggest():
    run_test("Suggest Python Syntax", {"code": "print('Hello'", "stderr": "SyntaxError: unexpected EOF while parsing", "language": "python"}, endpoint="/suggest")


# === INLINE FIX TESTS ===
def test_ai_inline():
    run_test("Inline Fix Python NameError", {"code": "prit('Hello, World!')", "stderr": "NameError: name 'prit' is not defined", "language": "python"}, endpoint="/suggest_inline")
    run_test("Inline Fix C Missing Semicolon", {"code": '#include <stdio.h>\nint main(){printf("Hi") return 0;}', "stderr": "error: expected ‘;’ before ‘return’", "language": "c"}, endpoint="/suggest_inline")
    run_test("Inline Fix Java Cannot Find Symbol", {"code": 'public class Main { public static void main(String[] args){ System.out.println(x); } }', "stderr": "error: cannot find symbol\nsymbol: variable x", "language": "java"}, endpoint="/suggest_inline")


# === EDGE TESTS ===
def test_edge():
    run_test("Empty Code", {"code": "", "stdin": "", "language": "python"}, expect_exit=0)
    run_test("Infinite Loop Timeout", {"code": "while True: pass", "stdin": "", "language": "python"}, expect_stderr="Execution timed out", expect_exit=-1)


if __name__ == "__main__":
    print("\n=== Running Backend Tests ===\n")

    test_python()
    test_c()
    test_cpp()
    test_java()
    test_ai_suggest()
    test_ai_inline()
    test_edge()

    print("\n=== All Tests Completed ===")
