# 🔐 AI-Powered Secure Code Runner

## 📌 Overview
The AI-Powered Secure Code Runner is a web-based system designed to safely execute user-submitted code in an isolated Docker environment. It focuses on security, scalability, and developer assistance by combining container-based sandboxing with AI-powered code analysis.

This project aims to demonstrate secure system design, backend engineering skills, and practical use of containerization for real-world applications.

---

## ✨ Key Features
- 🐳 Secure code execution using Docker sandboxing
- 🔒 Isolation to prevent unauthorized system access
- 🤖 AI-assisted code analysis and suggestions
- 🌐 Web-based interface for submitting and running code
- 📥 Input support and 📤 output capture
- 🧾 Execution logs and error handling

---

## 🛠 Tech Stack
- **Backend:** Python (FastAPI)
- **Frontend:** React.js
- **Containerization:** Docker
- **AI / Analysis:** Rule-based logic / Gemini API
- **Execution Environment:** Linux-based Docker containers
- **Tools:** Docker CLI

---

## 🏗 Architecture (High Level)
1. User submits code via web interface
2. Backend validates and forwards code
3. Code runs inside an isolated Docker container
4. Output and errors are captured securely
5. AI module analyzes code and provides feedback
6. Results are returned to the user

