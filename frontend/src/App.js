import React, { useState, useRef } from "react";
import Editor from "@monaco-editor/react";
import axios from "axios";
import "./App.css";

const BACKEND_URL = "http://localhost:8000"; // Local backend

function App() {
  const templates = {
    python: `# Python Example\nprint("Hello, World!")`,
    c: `#include <stdio.h>\nint main(){printf("Hello, World!\\n");return 0;}`,
    cpp: `#include <iostream>\nusing namespace std;\nint main(){cout<<"Hello, World!"<<endl;return 0;}`,
    java: `public class Main { public static void main(String[] args){ System.out.println("Hello, World!"); } }`,
  };

  const [language, setLanguage] = useState("python");
  const [code, setCode] = useState(templates.python);
  const [stdin, setStdin] = useState("");
  const [stdout, setStdout] = useState("");
  const [stderr, setStderr] = useState("");
  const [loading, setLoading] = useState(false);
  const [aiExplanation, setAiExplanation] = useState("");

  const editorRef = useRef(null);

  // === Run Code ===
  const runCode = async () => {
    setLoading(true);
    setStdout("");
    setStderr("");
    setAiExplanation("");

    try {
      const response = await axios.post(`${BACKEND_URL}/run`, {
        code,
        stdin,
        language,
      });

      setStdout(response.data.stdout || "");
      setStderr(response.data.stderr || "");
    } catch (err) {
      setStderr("⚠️ Backend error: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  // === Suggest Fix Button ===
  const handleSuggestFix = async () => {
    if (!stderr) return;
    try {
      const response = await axios.post(`${BACKEND_URL}/suggest`, {
        code,
        stderr,
        language,
      });
      setAiExplanation(response.data.suggestion || "⚠️ No suggestion.");
    } catch (err) {
      setAiExplanation("⚠️ Error fetching suggestion: " + err.message);
    }
  };

  // === Apply Fix Button ===
  const handleApplyFix = async () => {
    if (!stderr) return;
    try {
      const response = await axios.post(`${BACKEND_URL}/suggest_inline`, {
        code,
        stderr,
        language,
      });

      setCode(response.data.fixed_code || code);
      setAiExplanation(response.data.explanation || "");
    } catch (err) {
      setAiExplanation("⚠️ Error applying fix: " + err.message);
    }
  };

  const handleEditorDidMount = (editor) => {
    editorRef.current = editor;
  };

  const handleLanguageChange = (e) => {
    const newLang = e.target.value;
    setLanguage(newLang);
    setCode(templates[newLang]);
    setStdout("");
    setStderr("");
    setAiExplanation("");
  };

  return (
    <div className="app-root">
      <div className="navbar">
        <span className="logo">ai-secure-code-runner</span>
      </div>
      <div className="workspace">
        <div className="sidebar">Sidebar (future features)</div>

        <div className="editor-console">
          <div className="editor-section">
            <div className="toolbar">
              <select value={language} onChange={handleLanguageChange}>
                <option value="python">Python</option>
                <option value="c">C</option>
                <option value="cpp">C++</option>
                <option value="java">Java</option>
              </select>
              <button onClick={runCode} disabled={loading}>
                {loading ? "Running..." : "Run ▶"}
              </button>

              {stderr && (
                <>
                  <button onClick={handleSuggestFix}>💡 Suggest Fix</button>
                  <button onClick={handleApplyFix}>🛠 Apply Fix</button>
                </>
              )}
            </div>

            <Editor
              height="100%"
              language={language === "cpp" ? "cpp" : language}
              value={code}
              onChange={(value) => setCode(value || "")}
              onMount={handleEditorDidMount}
              theme="vs-dark"
            />
          </div>

          {aiExplanation && (
            <div className="ai-suggestion">
              <h3>AI Suggestion</h3>
              <pre>{aiExplanation}</pre>
            </div>
          )}

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
