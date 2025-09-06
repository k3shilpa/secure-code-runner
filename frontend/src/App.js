import React, { useState } from "react";
import Editor from "@monaco-editor/react";
import axios from "axios";
import "./App.css";

function App() {
  const [code, setCode] = useState("print('Hello, World!')");
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
        language: "python",
      });
      setStdout(response.data.stdout);
      setStderr(response.data.stderr);
    } catch (error) {
      setStderr("⚠️ Network/Server Error: " + error.message);
    }
    setLoading(false);
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
            <li className="active">main.py</li>
          </ul>
        </div>

        {/* Editor + Console */}
        <div className="editor-console">
          <div className="editor-section">
            <div className="toolbar">
              <button onClick={runCode} disabled={loading}>
                {loading ? "Running..." : "Run ▶"}
              </button>
            </div>
            <Editor
              height="100%"
              defaultLanguage="python"
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
