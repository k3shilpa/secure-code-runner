// App.js
import React, { useState, useRef, useEffect, useCallback } from "react";
import Editor from "@monaco-editor/react";
import axios from "axios";
import "./App.css";

const BACKEND_URL = "http://localhost:8000";

const templates = {
  python: `# Python Example\nprint("Hello, World!")`,
  c: `#include <stdio.h>\nint main(){printf("Hello, World!\\n");return 0;}`,
  cpp: `#include <iostream>\nusing namespace std;\nint main(){cout<<"Hello, World!"<<endl;return 0;}`,
  java: `public class Main { public static void main(String[] args){ System.out.println("Hello, World!"); } }`,
};

function App() {
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
  const [history, setHistory] = useState([]);
  const [filename, setFilename] = useState("untitled");

  const editorRef = useRef(null);

  // Generate unique filename
  const generateFilename = (lang = "code") => `${lang}_${Date.now()}`;

  // =========================
  // Run Code
  // =========================
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
        language: language === "auto" ? detectedLang || "python" : language,
      });

      setStdout(response.data.stdout || "");
      setStderr(response.data.stderr || "");
    } catch (err) {
      setStderr("⚠️ Backend error: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  // =========================
  // Apply AI Fix
  // =========================
  const handleApplyFix = async () => {
    if (!stderr) return;
    setLoading(true);
    try {
      const response = await axios.post(`${BACKEND_URL}/suggest_inline`, {
        code,
        stderr,
        language: language === "auto" ? detectedLang || "python" : language,
      });

      const fixedCode = response.data.fixed_code || code;
      const explanation = response.data.explanation || "";

      setAiExplanation(explanation);
      setAiFixedCode(fixedCode);
      setCode(fixedCode);
    } catch (err) {
      setAiExplanation("⚠️ Error applying fix: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleEditorDidMount = (editor) => {
    editorRef.current = editor;
  };

  // =========================
  // Language Change
  // =========================
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

      // Only load template if code area is empty
      if (!code.trim()) {
        setCode(templates[newLang] || "");
        if (!filename || filename.startsWith("untitled")) {
          setFilename(generateFilename(newLang));
        }
      }
    } else {
      // For auto-detect mode
      if (!filename.startsWith("untitled")) return;
      setFilename(generateFilename("code"));
    }
  };

  // =========================
  // Auto Detect Language
  // =========================
  useEffect(() => {
    if (language === "auto" && code.trim()) {
      const detectLanguage = async () => {
        try {
          const res = await axios.post(`${BACKEND_URL}/detect-language/`, { code });
          const detected = res.data.language;
          setDetectedLang(detected);
          setEditorLang(detected === "cpp" ? "cpp" : detected);

          if (res.data.load_template) {
            setCode(res.data.template || "");
            if (!filename || filename.startsWith("untitled")) {
              setFilename(generateFilename(detected));
            }
          }
        } catch (error) {
          console.error("Language detection failed:", error);
        }
      };

      detectLanguage();
    }
  }, [language, code, filename]);

  // =========================
  // Save Code
  // =========================
  const saveCode = async () => {
    if (!code.trim()) {
      alert("Code is empty — nothing to save!");
      return;
    }

    let name = filename.trim();
    if (!name || name.startsWith("untitled") || name === "") {
      name = prompt("Enter a filename:", filename || "untitled");
      if (!name) return;
    }

    setFilename(name);

    try {
      await axios.post(`${BACKEND_URL}/save_code`, {
        filename: name,
        code,
        language: language === "auto" ? detectedLang || "python" : language,
        stdout,
        stderr,
        ai_explanation: aiExplanation,
        ai_fixed_code: aiFixedCode,
      });
      alert(`💾 Saved as "${name}" successfully!`);
      loadHistory();
    } catch (err) {
      alert("⚠️ Failed to save: " + err.message);
    }
  };

  // =========================
  // Load History
  // =========================
  const loadSavedCode = (item) => {
    setFilename(item.filename || generateFilename(item.language));
    setLanguage(item.language);
    setEditorLang(item.language === "cpp" ? "cpp" : item.language);
    setCode(item.code);
    setStdout(item.stdout || "");
    setStderr(item.stderr || "");
    setAiExplanation(item.ai_explanation || "");
    setAiFixedCode(item.ai_fixed_code || "");
  };

  const loadHistory = useCallback(async () => {
    try {
      const res = await axios.get(`${BACKEND_URL}/history`);
      setHistory(res.data || []);
    } catch (err) {
      console.error("Failed to load history:", err.message);
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  return (
    <div className="app-root">
      <div className="navbar">
        <span className="logo">ai-secure-code-runner</span>
      </div>
      <div className="workspace">
        {/* Sidebar */}
        <div className="sidebar">
          <h3>💾 Saved Codes</h3>
          <button className="refresh-btn" onClick={loadHistory} disabled={loading}>
            🔄 Refresh
          </button>

          {history.length === 0 ? (
            <p className="empty-history">No saved codes yet.</p>
          ) : (
            history.map((item) => (
              <div
                key={item.id}
                className={`history-item ${item.filename === filename ? "active" : ""}`}
                onClick={() => loadSavedCode(item)}
              >
                <span className="file-icon">
                  {item.language === "python"
                    ? "🐍"
                    : item.language === "java"
                    ? "☕"
                    : item.language === "cpp"
                    ? "💠"
                    : item.language === "c"
                    ? "🧩"
                    : "📄"}
                </span>
                <span className="file-name">{item.filename || "untitled"}</span>
                
              </div>
            ))
          )}
        </div>

        {/* Editor + Console */}
        <div className="editor-console">
          <div className="editor-section">
            <div className="toolbar">
              <input
                type="text"
                placeholder="Enter file name..."
                value={filename}
                onChange={(e) => setFilename(e.target.value)}
                disabled={loading}
              />
              <select value={language} onChange={handleLanguageChange} disabled={loading}>
                <option value="auto">Auto Detect</option>
                <option value="python">Python</option>
                <option value="c">C</option>
                <option value="cpp">C++</option>
                <option value="java">Java</option>
              </select>
              <button onClick={runCode} disabled={loading}>
                {loading ? "Running..." : "Run ▶"}
              </button>
              {stderr && !loading && <button onClick={handleApplyFix}>🛠 Apply Fix</button>}
              <button onClick={saveCode} disabled={loading}>💾 Save Code</button>
            </div>

            {language === "auto" && detectedLang && (
              <div className="detected-lang">
                <strong>Detected Language:</strong> {detectedLang}
              </div>
            )}

            <Editor
              height="400px"
              language={editorLang}
              value={code}
              onChange={(value) => setCode(value || "")}
              onMount={handleEditorDidMount}
              theme="vs-dark"
              options={{ automaticLayout: true }}
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
            {!stdout && !stderr && <pre className="empty">Output will appear here...</pre>}

            <textarea
              className="stdin"
              placeholder="Type input here..."
              value={stdin}
              onChange={(e) => setStdin(e.target.value)}
              disabled={loading}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
