🌐 Live Demo: [your-vercel-url] (coming soon)
---

🚀 Archon — AI File Management Agent

Archon is an AI-powered file management system that can organi🌐 Live Demo: [your-vercel-url] (coming soon)ze, clean, and manage files automatically using a reasoning-based agent (ReAct loop).

It combines a Python FastAPI backend + Angular frontend to create a real-time, ChatGPT-style file assistant that actually acts on your system.

---

✨ What makes Archon different?

Unlike basic scripts, Archon thinks before acting:

🧠 AI Agent (ReAct Loop) → Plan → Act → Observe → Improve
🔒 Built-in Safety System → No risky file operations
👀 Dry Run First → See what will happen before executing
⚡ Real-time Streaming UI → Watch decisions live

---

🎯 What can it do?

📂 Organize files (Documents, Images, Code, etc.)
🧹 Clean folders intelligently
🔍 Find duplicates (based on content, not just name)
🗑️ Safe delete (recoverable, not permanent)
📋 List & search files quickly
🔄 Undo operations (session-based)

---

🏗️ Architecture (Simple View)

User Input (UI)
  ↓
Angular Frontend (Chat UI + Streaming)
  ↓
FastAPI Backend
  ↓
AI Orchestrator (ReAct Loop)
  ↓
Executor (Safety Layer)
  ↓
Tools (file operations)
  ↓
Live Response (WebSocket)

---

⚙️ Tech Stack

🧠 Backend
Python, FastAPI
Semantic Kernel
Groq (LLM)
WebSockets

🎨 Frontend
Angular 20 (standalone components)
Tailwind CSS
Real-time streaming chat UI
WebSocket-based live updates

---

🚀 Quick Start (5 mins)

1️⃣ Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Add API key
echo GROQ_API_KEY=your_key > .env

python main.py
```

👉 Runs at: [http://localhost:8000](http://localhost:8000)

2️⃣ Frontend

```bash
cd frontend
npm install
npm start
```

👉 Runs at: [http://localhost:4200](http://localhost:4200)

---

🧪 Example Commands

Try these in the UI:

“Clean my Downloads folder”
“Find duplicate files”
“Organize my Desktop”
“Find resume.pdf”

---

🔐 Safety First (Core Design)

Archon is designed to never break your system:

❌ Blocks system folders (C:\Windows, Program Files)
🔁 Uses soft delete (recycle_bin)
🧪 Defaults to dry run
📜 Keeps full session logs (audit trail)

---

🧠 How the AI Works

Archon uses a ReAct loop:

Understand goal
Choose next action
Execute tool
Observe result
Repeat until done (max 6 iterations)

This makes it:

smarter than scripts
safer than raw automation

---

🛠️ Key Features

🔌 Tool-based architecture (easy to extend)
⚡ WebSocket streaming logs
🧾 Session persistence
🔁 Undo support
📊 Structured observations for reasoning
🎯 Clean separation of backend (logic) and frontend (experience)

---

📁 Project Structure

```
Archon/
├── backend/      AI agent + API
├── frontend/     Angular UI (chat + streaming)
├── docs/         Architecture & notes
```

---

🧩 Adding New Features

Want to extend?

Add a new tool in app/tools/
It auto-registers
AI can instantly use it

---

## 🔧 Usage Tips

Agent feels slow
→ Large folders → expected (can optimize later)

No connection
→ Check backend is running on port 8000

Nothing happens
→ Try a simpler goal first

---

💡 Why this project matters

Archon is not just file automation — it’s:

👉 A foundation for autonomous systems
👉 A safe AI agent architecture
👉 A real-world application of LLM reasoning

---

📌 Future Scope

Smarter planning (fewer steps)
Faster duplicate detection
Cross-platform support
Voice-based interaction

---

❤️ Final Note

Built to explore how AI agents can safely interact with real systems — not just chat.
