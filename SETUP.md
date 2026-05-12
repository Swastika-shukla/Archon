# Archon Project - Complete Setup Guide

This guide covers setting up and running the entire Archon project (backend + frontend).

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Project Structure](#project-structure)
3. [Backend Setup](#backend-setup)
4. [Frontend Setup](#frontend-setup)
5. [Running Both Services](#running-both-services)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)

## Prerequisites

- **Python 3.11+** (for backend)
- **Node.js 18+** and npm (for frontend)
- **Groq API Key** (get from https://console.groq.com)
- **Git** (for version control)
- **Windows** (for file operations)

### Verify Installations

```bash
# Check Python
python --version

# Check Node/npm
node --version
npm --version

# Check Git
git --version
```

## Project Structure

```
Archon/
├── backend/                 Python AI agent backend
│   ├── app/                Agent logic, tools, API
│   ├── memory/             Persisted session states
│   ├── main.py             FastAPI server entry
│   ├── requirements.txt     Python dependencies
│   ├── .env.example        Environment template
│   └── README.md           Backend documentation
│
├── frontend/               Angular UI frontend
│   ├── src/               Angular source code
│   ├── package.json        npm dependencies
│   ├── angular.json        Angular config
│   ├── tailwind.config.js  Tailwind config
│   └── README.md           Frontend documentation
│
├── docs/                   Documentation
│   ├── AGENTS.md          Agent instructions
│   ├── architecture.md    System design
│   └── project_context.md Project vision
│
├── .env.example           Root environment template
├── .gitignore             Git ignore rules
├── README.md              Project overview
└── SETUP.md               This file
```

## Backend Setup

### 1. Navigate to Backend Directory

```bash
cd backend
```

### 2. Create Python Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
# Copy the template
copy .env.example .env

# Edit .env and add your Groq API key
# Open .env in your editor and update:
# GROQ_API_KEY=your_actual_key_here
```

### 5. Verify Setup

```bash
# Test imports
python -c "import semantic_kernel; print('SK installed')"

# Check configuration
echo %GROQ_API_KEY%  # Should show your key (Windows)
# echo $GROQ_API_KEY  # Linux/Mac
```

### 6. Run Backend Server

```bash
python main.py
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

### 7. Verify Backend

Open in browser:
- **API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **API Health**: http://localhost:8000/api/tools

## Frontend Setup

### 1. Open New Terminal and Navigate to Frontend

```bash
cd frontend
```

### 2. Install Dependencies

```bash
npm install
```

This will install:
- Angular 17
- Tailwind CSS 3.3
- TypeScript 5.2
- And all other dependencies

### 3. Configure Environment (Optional)

Backend is at `localhost:8000` by default. If different, edit:

```bash
# Edit src/environments/environment.ts
# Update apiWebSocketUrl and apiHttpUrl as needed
```

### 4. Run Frontend Dev Server

```bash
npm start
```

You should see:
```
✔ Compiled successfully.
✔ Build complete. Watching for changes...

Application bundle generated successfully.
The serve command has started watching for file changes. To stop the serve process, press `y` + Enter.

→ Local:   http://localhost:4200
```

### 5. Open in Browser

Navigate to: http://localhost:4200

You should see the Archon UI with a clean, modern interface.

## Running Both Services

### Terminal 1: Backend

```bash
cd backend
venv\Scripts\activate
python main.py
```

### Terminal 2: Frontend

```bash
cd frontend
npm start
```

### Terminal 3 (Optional): Monitor Logs

```bash
# Monitor backend logs
cd backend
tail -f memory/*/observations  # Linux/Mac
# dir memory\  # Windows (list session files)

# Or check recent session
cd backend
type memory\*.json | more  # Windows
# cat memory/*.json | head -100  # Linux/Mac
```

## Testing

### Test Backend

```bash
cd backend
python test_state.py
```

This runs a full integration test of the agent loop.

### Test Frontend

```bash
cd frontend
npm test
```

### Test API Manually

```bash
# HTTP Request
curl -X POST http://localhost:8000/api/run \
  -H "Content-Type: application/json" \
  -d '{"goal": "List files in C:/Users/HP/Downloads", "dry_run": true}'

# Or use the web UI at http://localhost:4200
```

### Test WebSocket (Advanced)

```bash
# Use browser DevTools Console
const ws = new WebSocket('ws://localhost:8000/ws/run');
ws.onopen = () => ws.send(JSON.stringify({goal: "Test", dry_run: true}));
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

## Common Workflows

### Add a New Tool (Backend)

1. Create `backend/app/tools/my_tool.py`
2. Inherit from `BaseTool`
3. Implement required methods
4. Restart backend—auto-discovered
5. Available to LLM immediately

See [backend/README.md](backend/README.md) for template.

### Customize LLM Behavior (Backend)

Edit system prompt in `backend/app/agent/orchestrator.py`

### Modify UI (Frontend)

1. Edit `frontend/src/app/app.component.ts` for logic
2. Edit `frontend/src/app/app.component.html` for template
3. Add Tailwind classes for styling
4. Restart dev server (auto-reload)

### Deploy to Production

See individual README files:
- [backend/README.md](backend/README.md#deployment)
- [frontend/README.md](frontend/README.md#deployment)

## Troubleshooting

### Python: ModuleNotFoundError

```bash
# Ensure venv is activated
venv\Scripts\activate

# Reinstall requirements
pip install -r requirements.txt
```

### Python: GROQ_API_KEY not found

```bash
# Check .env exists
dir .env

# Check it has content
type .env

# Make sure it has your actual API key
```

### Node: npm install fails

```bash
# Clear npm cache
npm cache clean --force

# Remove node_modules and package-lock
rm -rf node_modules package-lock.json

# Reinstall
npm install
```

### WebSocket: Connection refused

- Ensure backend is running: `python main.py`
- Check backend is on `localhost:8000`
- Check firewall allows the connection
- Try direct curl: `curl http://localhost:8000/docs`

### Frontend: Blank page

- Check browser console (F12) for errors
- Verify backend is running
- Try clearing cache: `Ctrl+Shift+Delete`
- Check network tab for failed requests

### Agent: Stuck/Timeout

- Max iterations: 10 (configurable in `orchestrator.py`)
- Try simpler goals first
- Check backend logs for errors
- Restart backend if needed

## Port Conflicts

If ports are already in use:

### Backend (Port 8000)

```bash
# Find process using port 8000
netstat -ano | findstr :8000  # Windows
# lsof -i :8000  # Linux/Mac

# Change port in backend/main.py or run with:
uvicorn main:app --port 8001
```

### Frontend (Port 4200)

```bash
# Run on different port
ng serve --port 4201

# Or change default in angular.json
# "serve": { "options": { "port": 4201 } }
```

## Environment Variables Reference

| Variable | Location | Purpose | Example |
|----------|----------|---------|---------|
| `GROQ_API_KEY` | backend/.env | LLM API key | `gsk_...` |
| `GROQ_MODEL` | backend/.env | LLM model | `llama-3.3-70b-versatile` |
| `HOST` | backend/.env | Server host | `0.0.0.0` |
| `PORT` | backend/.env | Server port | `8000` |
| `ARCHON_API_URL` | frontend/.env | Backend WS URL | `ws://localhost:8000/ws/run` |
| `ARCHON_HTTP_URL` | frontend/.env | Backend API URL | `http://localhost:8000/api` |

## Next Steps

1. ✅ Backend running at `localhost:8000`
2. ✅ Frontend running at `localhost:4200`
3. **Explore the UI** – Enter a goal and run the agent
4. **Check logs** – View execution logs in backend `memory/` folder
5. **Add tools** – See `backend/README.md` for tool development
6. **Customize UI** – See `frontend/README.md` for UI modifications
7. **Deploy** – See individual README files for deployment guides

## Documentation

- [Project Overview](README.md)
- [Backend Documentation](backend/README.md)
- [Frontend Documentation](frontend/README.md)
- [Agent Instructions](docs/AGENTS.md)
- [Architecture](docs/architecture.md)
- [Project Context](docs/project_context.md)

## Support

### Check Logs

```bash
# Backend
cd backend
tail -f memory/latest.log  # Or check memory/{session_id}.json

# Frontend
# Open browser DevTools (F12) → Console
```

### Common Issues

1. **Backend won't start**
   - Check Python 3.11+: `python --version`
   - Check GROQ_API_KEY in .env
   - Try: `pip install -r requirements.txt --upgrade`

2. **Frontend won't connect**
   - Check backend is running: `curl http://localhost:8000/docs`
   - Check WebSocket URL in `src/environments/environment.ts`
   - Check browser console for errors

3. **Agent stuck**
   - Max iterations: 10
   - Try simpler goal
   - Check backend logs
   - Restart backend

## Quick Reference

```bash
# Terminal 1: Backend
cd backend
venv\Scripts\activate
python main.py
# → http://localhost:8000/docs

# Terminal 2: Frontend
cd frontend
npm start
# → http://localhost:4200

# Terminal 3: Tests
cd backend
python test_state.py
```

---

**Questions?** See the individual README files or check the documentation in `docs/`.

**Ready to deploy?** See deployment sections in [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md).
