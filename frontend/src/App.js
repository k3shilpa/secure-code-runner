import React, { useState } from "react";
import Editor from "@monaco-editor/react";
import axios from "axios";
import "./App.css";

function App() {
  const templates = {
    python: "print('Hello, World!')",
    c: "#include <stdio.h>\nint main() {\n    printf(\"Hello, World!\\n\");\n    return 0;\n}",
    cpp: "#include <iostream>\nusing namespace std;\nint main() {\n    cout << \"Hello, World!\" << endl;\n    return 0;\n}",
    java: "public class Main {\n    public static void main(String[] args) {\n        System.out.println(\"Hello, World!\");\n    }\n}",
  };

  const [language, setLanguage] = useState("python");
  const [code, setCode] = useState(templates.python);
  const [stdin, setStdin] = useState("");
  const [stdout, setStdout] = useState("");
  const [stderr, setStderr] = useState("");
  const [loading, setLoading] = useState(false);

  const runCode = async () => {
    setLoading(true);
    setStdout("");
    setStderr("");
    try {
      const response = await axios.post("http://127.0.0.1:8000/run", {
        code,
        stdin,
        language,
      });
      setStdout(response.data.stdout);
      setStderr(response.data.stderr);
    } catch (error) {
      setStderr("⚠️ Network/Server Error: " + error.message);
    }
    setLoading(false);
  };

  const handleLanguageChange = (e) => {
    const newLang = e.target.value;
    setLanguage(newLang);
    setCode(templates[newLang]); // ✅ load Hello World template automatically
  };

  return (
    <div className="app-root">
      {/* === Top Navbar === */}
      <div className="navbar">
        <span className="logo">ai-secure-code-runner</span>
      </div>

      {/* === Main Workspace === */}
      <div className="workspace">
        {/* Sidebar */}
        <div className="sidebar">
          <h3>Files</h3>
          <ul>
            <li className="active">
              {language === "python" && "main.py"}
              {language === "c" && "main.c"}
              {language === "cpp" && "main.cpp"}
              {language === "java" && "Main.java"}
            </li>
          </ul>
        </div>

        {/* Editor + Console */}
        <div className="editor-console">
          <div className="editor-section">
            <div className="toolbar">
              {/* ✅ Language Dropdown */}
              <select value={language} onChange={handleLanguageChange}>
                <option value="python">Python</option>
                <option value="c">C</option>
                <option value="cpp">C++</option>
                <option value="java">Java</option>
              </select>

              <button onClick={runCode} disabled={loading}>
                {loading ? "Running..." : "Run ▶"}
              </button>
            </div>

            <Editor
              height="100%"
              language={language === "cpp" ? "cpp" : language}
              value={code}
              onChange={(value) => setCode(value)}
              theme="vs-dark"
            />
          </div>

          <div className="console-section">
            <h3>Console</h3>
            {stdout && <pre className="stdout">{stdout}</pre>}
            {stderr && <pre className="stderr">{stderr}</pre>}
            {!stdout && !stderr && (
              <pre className="empty">Output will appear here...</pre>
            )}
            <textarea
              className="stdin"
              placeholder="Type input here..."
              value={stdin}
              onChange={(e) => setStdin(e.target.value)}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
