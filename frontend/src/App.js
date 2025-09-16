import React, { useState, useRef, useCallback } from "react";
import Editor from "@monaco-editor/react";
import axios from "axios";
import * as monaco from "monaco-editor";
import "./App.css";

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
  const decorationsRef = useRef([]);

  // === Run Code ===
  const runCode = async () => {
    setLoading(true);
    setStdout("");
    setStderr("");
    setAiExplanation("");

    try {
      const response = await axios.post("http://127.0.0.1:8000/run", {
        code,
        stdin,
        language,
      });

      setStdout(response.data.stdout || "");
      setStderr(response.data.stderr || "");

      if (response.data.stderr) {
        fetchInlineSuggestion(code, response.data.stderr);
      }
    } catch (err) {
      setStderr("⚠️ Backend error: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  // === Inline Ghost Suggestion ===
  const fetchInlineSuggestion = useCallback(
    async (currentCode, currentError) => {
      if (!currentError) return;
      try {
        const response = await axios.post("http://127.0.0.1:8000/suggest_inline", {
          code: currentCode,
          stderr: currentError,
          language,
        });

        const fixedCode = response.data.fixed_code || "";
        const explanation = response.data.explanation || "";

        setAiExplanation(explanation);

        if (editorRef.current && explanation) {
          const editor = editorRef.current;
          const lineCount = editor.getModel().getLineCount();

          decorationsRef.current = editor.deltaDecorations(
            decorationsRef.current,
            [
              {
                range: new monaco.Range(lineCount, 1, lineCount, 1),
                options: {
                  isWholeLine: true,
                  after: {
                    content: "💡 " + explanation,
                    inlineClassName: "ghost-text",
                  },
                },
              },
            ]
          );
        }
      } catch (error) {
        console.error("Inline suggestion error:", error.message);
      }
    },
    [language]
  );

  // === Suggest Fix Button ===
  const handleSuggestFix = async () => {
    if (!stderr) return;
    try {
      const response = await axios.post("http://127.0.0.1:8000/suggest", {
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
      const response = await axios.post("http://127.0.0.1:8000/suggest_inline", {
        code,
        stderr,
        language,
      });

      const fixedCode = response.data.fixed_code || code;
      const explanation = response.data.explanation || "";

      setCode(fixedCode);
      setAiExplanation(explanation);
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
        {/* Sidebar */}
        <div className="sidebar">Sidebar (future features)</div>

        {/* Editor + Console */}
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

              {/* Show these only if there's an error */}
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

          {/* AI Suggestions */}
          {aiExplanation && (
            <div className="ai-suggestion">
              <h3>AI Suggestion</h3>
              <pre>{aiExplanation}</pre>
            </div>
          )}

          {/* Console */}
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
