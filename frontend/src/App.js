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
  const [history, setHistory] = useState([]);

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

  // === Save code to backend ===
  const saveCode = async () => {
    try {
      await axios.post(`${BACKEND_URL}/save_code`, {
        code,
        language: language === "auto" ? (detectedLang || "python") : language,
        stdout,
        stderr,
        ai_explanation: aiExplanation,
        ai_fixed_code: aiFixedCode,
      });
      alert("Code saved successfully!");
      loadHistory();
    } catch (err) {
      alert("Failed to save code: " + err.message);
    }
  };

  // === Load history from backend ===
  const loadHistory = async () => {
    try {
      const res = await axios.get(`${BACKEND_URL}/history`);
      setHistory(res.data || []);
    } catch (err) {
      console.error("Failed to load history:", err.message);
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  return (
    <div className="app-root">
      <div className="navbar">
        <span className="logo">ai-secure-code-runner</span>
      </div>
      <div className="workspace">
        <div className="sidebar">
          <button onClick={loadHistory}>🔄 Refresh History</button>
          <h3>Previous Codes</h3>
          {history.length === 0 && <p>No saved code yet.</p>}
          <ul>
            {history.map((item) => (
              <li key={item.id}>
                <button
                  onClick={() => {
                    setCode(item.code);
                    setLanguage(item.language);
                    setEditorLang(item.language === "cpp" ? "cpp" : item.language);
                    setStdout(item.stdout);
                    setStderr(item.stderr);
                    setAiExplanation(item.ai_explanation);
                    setAiFixedCode(item.ai_fixed_code);
                  }}
                >
                  {item.language} - ID {item.id}
                </button>
              </li>
            ))}
          </ul>
        </div>

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

              <button onClick={saveCode}>💾 Save Code</button>
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
