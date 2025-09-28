# test_suggestion.py

import requests

BASE_URL = "http://127.0.0.1:8000"

# ========================
# Test cases for all languages
# ========================
test_cases = [
    # ----------------
    # Python
    # ----------------
    {"language": "python", "code": "print('Hello'", "stderr": "SyntaxError: unexpected EOF while parsing"},
    {"language": "python", "code": "prit('Hello')", "stderr": "NameError: name 'prit' is not defined"},
    {"language": "python", "code": "1/0", "stderr": "ZeroDivisionError: division by zero"},
    {"language": "python", "code": "def f(): return f()\nf()", "stderr": "RecursionError: maximum recursion depth exceeded"},
    {"language": "python", "code": "for i in range(5)\n    print(i)", "stderr": "SyntaxError: invalid syntax"},
    {"language": "python", "code": "a = '1'\nb = a + 2", "stderr": "TypeError: can only concatenate str (not \"int\") to str"},
    {"language": "python", "code": "import math\nmath.sqrt(-1)", "stderr": "ValueError: math domain error"},
    {"language": "python", "code": "my_list = [1,2]\nprint(my_list[5])", "stderr": "IndexError: list index out of range"},
    {"language": "python", "code": "my_dict = {}\nprint(my_dict['key'])", "stderr": "KeyError: 'key'"},
    {"language": "python", "code": "x = 10\ny = undefined_var", "stderr": "NameError: name 'undefined_var' is not defined"},

    # ----------------
    # C
    # ----------------
    {"language": "c", "code": "#include <stdio.h>\nint main(){printf(\"Hi\") return 0;}", "stderr": "error: expected ';' before 'return'"},
    {"language": "c", "code": "int main(){int *p = NULL; *p = 5; return 0;}", "stderr": "Segmentation fault"},
    {"language": "c", "code": "int main(){int x=5/0; return 0;}", "stderr": "Floating point exception"},
    {"language": "c", "code": "int main(){int a = 'a' + 1; return 0;}", "stderr": "warning: character constant too long for its type"},
    {"language": "c", "code": "int main(){int a = 1; if(a==1) return 0;", "stderr": "error: expected '}' before end of input"},

    # ----------------
    # C++
    # ----------------
    {"language": "cpp", "code": "#include <iostream>\nint main(){std::cout << 'Hi' return 0;}", "stderr": "error: expected ';' before 'return'"},
    {"language": "cpp", "code": "int main(){int *p = nullptr; *p = 5; return 0;}", "stderr": "Segmentation fault"},
    {"language": "cpp", "code": "int main(){int x=5/0; return 0;}", "stderr": "Floating point exception"},
    {"language": "cpp", "code": "int main(){std::string s; std::cout << s[5]; return 0;}", "stderr": "std::out_of_range"},
    {"language": "cpp", "code": "int main(){int a = 'a' + 1; return 0;}", "stderr": "warning: character constant too long for its type"},

    # ----------------
    # Java
    # ----------------
    {"language": "java", "code": "public class Main{public static void main(String[] args){System.out.println(x);}}", "stderr": "cannot find symbol"},
    {"language": "java", "code": "public class Main{public static void main(String[] args){int a = 1/0;}}", "stderr": "ArithmeticException: / by zero"},
    {"language": "java", "code": "public class Main{public static void main(String[] args){System.out.println('Hi')}}", "stderr": "error: ';' expected"},
    {"language": "java", "code": "public class Main{public static void main(String[] args){int[] arr = new int[2]; System.out.println(arr[5]);}}", "stderr": "ArrayIndexOutOfBoundsException"},
    {"language": "java", "code": "public class Main{public static void main(String[] args){String s = null; System.out.println(s.length());}}", "stderr": "NullPointerException"},
]

# ========================
# Testing function
# ========================
def test_endpoint(endpoint: str):
    print(f"\n=== Testing {endpoint} Endpoint ===\n")
    for i, test in enumerate(test_cases, 1):
        payload = {
            "code": test["code"],
            "stderr": test["stderr"],
            "language": test["language"]
        }
        try:
            response = requests.post(f"{BASE_URL}/{endpoint}", json=payload)
            result = response.json()
        except Exception as e:
            result = {"error": str(e)}

        print(f"Test {i}: {test['language']} error: {test['stderr']}")
        if endpoint == "suggest":
            print("AI Suggestion:")
            print(result.get("suggestion", result))
        else:
            print("Explanation:")
            print(result.get("explanation", result))
            print("Fixed Code:")
            print(result.get("fixed_code", test["code"]))
        print("-" * 80)

# ========================
# Run tests for both endpoints
# ========================
if __name__ == "__main__":
    test_endpoint("suggest")
    test_endpoint("suggest_inline")
