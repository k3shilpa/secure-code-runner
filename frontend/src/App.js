// App.js
import React, { useState, useRef, useEffect } from "react";
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
  const [editorLang, setEditorLang] = useState("python"); 
  const [code, setCode] = useState(templates.python);
  const [stdin, setStdin] = useState("");
  const [stdout, setStdout] = useState("");
  const [stderr, setStderr] = useState("");
  const [loading, setLoading] = useState(false);
  const [aiExplanation, setAiExplanation] = useState("");
  const [aiFixedCode, setAiFixedCode] = useState("");
  const [detectedLang, setDetectedLang] = useState("");
  const [autoLoaded, setAutoLoaded] = useState(false);

  const editorRef = useRef(null);

  // === Run Code ===
  const runCode = async () => {
    setLoading(true);
    setStdout("");
    setStderr("");
    setAiExplanation("");
    setAiFixedCode("");

    try {
      const response = await axios.post(`${BACKEND_URL}/run`, {
        code,
        stdin,
        language: language === "auto" ? (detectedLang || "python") : language,
      });

      setStdout(response.data.stdout || "");
      setStderr(response.data.stderr || "");
    } catch (err) {
      setStderr("⚠️ Backend error: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  // === Apply Fix Button ===
  const handleApplyFix = async () => {
    if (!stderr) return;
    try {
      const response = await axios.post(`${BACKEND_URL}/suggest_inline`, {
        code,
        stderr,
        language: language === "auto" ? (detectedLang || "python") : language,
      });

      const fixedCode = response.data.fixed_code || code;
      const explanation = response.data.explanation || "";

      setAiExplanation(explanation);
      setAiFixedCode(fixedCode);

      setCode(fixedCode);
      if (editorRef.current) {
        editorRef.current.setValue(fixedCode);
      }
    } catch (err) {
      setAiExplanation("⚠️ Error applying fix: " + err.message);
    }
  };

  const handleEditorDidMount = (editor) => {
    editorRef.current = editor;
  };

  // === Language change handler ===
  const handleLanguageChange = (e) => {
    const newLang = e.target.value;
    setLanguage(newLang);
    setStdout("");
    setStderr("");
    setAiExplanation("");
    setAiFixedCode("");
    setDetectedLang("");

    if (newLang !== "auto") {
      setEditorLang(newLang === "cpp" ? "cpp" : newLang);

      if (!code.trim()) {
        setCode(templates[newLang] || "");
        setAutoLoaded(true);
      } else {
        setAutoLoaded(false);
      }
    }
  };

  // === Auto-detect when code changes ===
  useEffect(() => {
    const detectLang = async () => {
      if (language !== "auto") return;
      try {
        const res = await axios.post(`${BACKEND_URL}/detect_language`, {
          code,
          auto_loaded: autoLoaded,
        });
        const detected = res.data.language;
        setDetectedLang(detected);
        setEditorLang(detected === "cpp" ? "cpp" : detected);

        if (res.data.load_template && res.data.template) {
          setCode(res.data.template);
          setAutoLoaded(true);
        }
      } catch (err) {
        console.error("Detection failed:", err.message);
      }
    };

    detectLang();
  }, [code, language, autoLoaded]);

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
                <option value="auto">Auto Detect</option>
                <option value="python">Python</option>
                <option value="c">C</option>
                <option value="cpp">C++</option>
                <option value="java">Java</option>
              </select>
              <button onClick={runCode} disabled={loading}>
                {loading ? "Running..." : "Run ▶"}
              </button>

              {stderr && (
                <button onClick={handleApplyFix}>🛠 Apply Fix</button>
              )}
            </div>

            {language === "auto" && detectedLang && (
              <div className="detected-lang">
                <strong>Detected Language:</strong> {detectedLang}
              </div>
            )}

            <Editor
              height="100%"
              language={editorLang}
              value={code}
              onChange={(value) => setCode(value || "")}
              onMount={handleEditorDidMount}
              theme="vs-dark"
            />
          </div>

          {(aiExplanation || aiFixedCode) && (
            <div className="ai-suggestion">
              <h3>AI Suggestion</h3>
              {aiExplanation && <p>{aiExplanation}</p>}
              {aiFixedCode && (
                <>
                  <h4>Fixed Code:</h4>
                  <pre>{aiFixedCode}</pre>
                </>
              )}
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
