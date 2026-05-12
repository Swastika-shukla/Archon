# PROJECT_CONTEXT.md
> Single source of truth for the Archon project.
> Last updated: April 2026

---

## 1. Project Overview

**Project Name:** Archon
**Type:** AI-powered file management agent
**Stack:** Python 3.11 · FastAPI · Semantic Kernel · Groq (Llama 3.3) · Angular (pending)

### What It Does
Archon is a local AI agent that accepts a natural language goal from the user and autonomously plans and executes file management tasks on the user's Windows machine. It uses a ReAct-style agentic loop (Plan → Act → Observe → Update) powered by Llama 3.3 via Groq to dynamically decide which tools to call at each step.

### Core Goal
Allow a non-technical user to say something like:
> "Clean my Downloads folder"

And have Archon intelligently:
1. Scan for duplicate files
2. Categorize files by type
3. Move files into organized subfolders
4. Safely delete duplicates

All with dry-run mode enabled by default — no real changes until the user explicitly allows it.

---

## 2. Current Capabilities

### What the Agent Can Do Today
- Accept a natural language goal via API
- Dynamically plan which tools to call using Llama 3.3
- Execute tools safely through a multi-gate Executor
- Detect duplicate files using SHA-256 content hashing
- Categorize files by extension into typed groups
- Move files with full undo logging
- Soft-delete files to a recoverable recycle bin
- Simulate all operations in dry-run mode without touching real files
- Persist full session state to local JSON after every step
- Retrieve past sessions via API
- Provide structured, LLM-readable observations after every tool call
- Block operations on protected system paths at code level
- Retry failed tool calls with exponential backoff

---

## 3. Implemented Components

### Agent Controller (`app/agent/controller.py`)
- Entry point between the API and the agent
- Validates the goal (not empty, 10–500 characters)
- Creates a fresh `AgentState` with a unique session ID
- Calls `Orchestrator.run()` and returns the final state
- Exposes `run_sync()` for non-async contexts

### Orchestrator — ReAct Loop (`app/agent/orchestrator.py`)
- Implements the full Plan → Act → Observe → Update loop
- Manages `ChatHistory` across all loop iterations
- Sends current state to Groq via Semantic Kernel
- Parses LLM JSON response to extract action + params
- Creates `TaskStep` and passes to Executor
- Builds rich structured observations from tool results
- Feeds observations back into chat history for next iteration
- Stops when LLM returns `"action": "finish"` or MAX_ITERATIONS (10) reached
- Saves state after every step

### Executor (`app/core/executor.py`)
- The ONLY component that directly calls tools
- Runs 4 sequential checks before every tool call:
  1. Tool exists in registry
  2. Required params are present
  3. All paths are safe (not system folders)
  4. Dry-run mode respected
- Retries on failure: max 3 attempts, exponential backoff (2s, 4s, 6s)
- Updates AgentState with result or error after every call
- Saves state to disk after every successful execution

### Tool Registry (`app/tools/__init__.py`)
- Manual registry mapping tool name strings to tool instances
- `get_tool(name)` → returns tool instance or None
- `list_tools()` → returns all tools with name, description, parameters
- This list is sent to the LLM in the system prompt so it knows what tools exist
- **Status:** Manual registration. Auto-discovery pending (Phase 1 Step 2).

### AgentState (`app/agent/state.py`)
- Central dataclass passed between all layers
- Persists to `memory/{session_id}.json` after every step
- Full schema documented in Section 7 below

### FastAPI Server (`app/api/routes.py` + `main.py`)
- `POST /api/run` → runs agent with goal + dry_run flag
- `GET /api/status/{session_id}` → retrieves saved session state
- `GET /api/sessions` → lists all past session IDs
- `DELETE /api/session/{session_id}` → deletes a session
- `GET /api/tools` → lists all registered tools
- `GET /api/health` → health check
- CORS configured for Angular (localhost:4200)
- Auto-generated Swagger UI at `/docs`

### Semantic Kernel (`app/agent/kernel.py`)
- Configures SK Kernel using `OpenAIChatCompletion`
- Points at Groq's API URL instead of OpenAI's (compatible format)
- Returns a ready-to-use kernel instance
- Used by Orchestrator to send ChatHistory to Groq and receive decisions

### Groq Integration
- Model: `llama-3.3-70b-versatile`
- Free tier, no credit card required
- API key stored in `.env` as `GROQ_API_KEY`
- Temperature: 0.1 (near-deterministic for consistent JSON output)
- Max tokens: 500 per LLM call

---

## 4. Tools — Detailed

### `detect_duplicates`
- **Purpose:** Find files with identical content in a folder
- **Method:** SHA-256 hashing (reads in 8KB chunks to avoid RAM overload)
- **Input:**
  - `path` (str, required) — folder to scan
  - `recursive` (bool, optional, default False) — scan subfolders
- **Dry-run behavior:** Counts files only, skips hashing for speed
- **Live behavior:** Hashes every file, groups by hash, identifies duplicates
- **Output:**
  ```json
  {
    "total_files_scanned": 1333,
    "total_duplicate_files": 94,
    "total_duplicate_groups": 47,
    "duplicates": [
      {
        "hash": "a3f8c2d1e9b4...",
        "count": 2,
        "files": ["path/to/file1.jpg", "path/to/file2.jpg"],
        "keep": "path/to/file1.jpg",
        "remove": ["path/to/file2.jpg"]
      }
    ]
  }
  ```

### `categorize_files`
- **Purpose:** Group files in a folder by their type/extension
- **Categories:** Images, Videos, Audio, Documents, Archives, Code, Executables, Others
- **Input:**
  - `path` (str, required) — folder to categorize
- **Dry-run behavior:** Same as live (read-only operation, safe always)
- **Output:**
  ```json
  {
    "total_files": 1333,
    "categories_found": ["Documents", "Images", "Videos"],
    "categorized": {
      "Images": [
        {
          "filename": "photo.jpg",
          "full_path": "C:/Users/HP/Downloads/photo.jpg",
          "destination": "C:/Users/HP/Downloads/Images/photo.jpg"
        }
      ]
    }
  }
  ```

### `move_files`
- **Purpose:** Move files from source paths to a destination folder
- **Input:**
  - `files` (list, required) — list of full file paths to move
  - `destination` (str, required) — target folder
- **Dry-run behavior:** Simulates move, records what would happen
- **Live behavior:** Uses `shutil.move()`, creates destination if needed, skips conflicts
- **Undo log:** Every live move is recorded as `{from: dest_path, to: original_path}`
- **Output:**
  ```json
  {
    "total_moved": 45,
    "total_skipped": 3,
    "moved": [{"from": "...", "to": "...", "status": "moved"}],
    "skipped": [{"file": "...", "reason": "File already exists at destination"}],
    "undo_log": [{"from": "dest/file.jpg", "to": "original/file.jpg"}]
  }
  ```

### `safe_delete`
- **Purpose:** Soft-delete files by moving to `recycle_bin/` folder (never permanent)
- **Input:**
  - `files` (list, required) — list of full file paths to delete
- **Dry-run behavior:** Simulates deletion, shows what would be moved to bin
- **Live behavior:** Moves files to `recycle_bin/{timestamp}_{filename}`
- **Recovery:** Files always recoverable from `recycle_bin/`
- **Output:**
  ```json
  {
    "total_deleted": 94,
    "total_skipped": 2,
    "recycle_bin": "recycle_bin",
    "deleted": [{"original": "...", "bin_path": "...", "status": "moved_to_bin"}],
    "skipped": [{"file": "...", "reason": "File not found"}]
  }
  ```

---

## 5. Safety System

### Dry-Run Mode
- Default: `dry_run=True` everywhere
- Every tool accepts `dry_run` parameter
- In dry-run: tools simulate operations, return what WOULD happen
- No disk writes in dry-run mode
- User must explicitly pass `dry_run=False` for real changes

### Permission Guard (`app/core/safety.py`)
- Blocked paths (hardcoded, cannot be overridden by LLM):
  - `C:/Windows`
  - `C:/Program Files`
  - `C:/Program Files (x86)`
  - `C:/ProgramData`
  - `~/.ssh`
  - `~/AppData/Roaming`
  - `~/AppData/Local/Microsoft`
- Path normalization before checking (catches case variations)
- All path-like params extracted and checked: `path`, `source`, `destination`, `target`, `folder`, `files`
- Enforced in code, not just in LLM prompt (LLM ignored prompt-level rules during testing)

### Retry Logic
- Max 3 attempts per tool call
- Exponential backoff: 2s → 4s → 6s
- Handles transient failures (locked files, permissions)
- After 3 failures: step marked failed, error fed back to LLM as observation

### Undo Logging
- `move_files` records every live move in `undo_log` inside tool result
- `undo_log` saved inside session JSON in `memory/`
- **Status:** Undo data exists. `/api/undo/{session_id}` endpoint pending (Phase 1 Step 3)

---

## 6. Agent Behavior

### The ReAct Loop
```
INITIALIZE:
  AgentState created with goal + session_id
  ChatHistory initialized with system prompt
  System prompt contains: tool list, Windows paths, JSON response rules, safety rules

LOOP (max 10 iterations):

  PLAN:
    Send full ChatHistory to Groq via SK
    LLM reads: system prompt + goal + all previous observations
    LLM responds with JSON: {action, params, reasoning}

  ACT:
    Parse LLM JSON response
    Create TaskStep from action + params
    Pass to Executor:
      → validate tool exists
      → validate params
      → check path safety
      → respect dry_run flag
      → execute tool
      → retry on failure

  OBSERVE:
    Build structured observation from tool result
    Different observation template per tool (detect_duplicates, categorize_files, etc.)
    Observation includes: counts, insights, recommended next action

  UPDATE:
    Add observation to ChatHistory
    Update AgentState (completed_steps, results, observations)
    Save state to memory/{session_id}.json
    Loop back to PLAN

FINISH:
  LLM returns {"action": "finish"}
  OR max iterations (10) reached
  AgentState.status = COMPLETED
  Final save to memory/
```

### How Tool Selection Works
- LLM reads the full tool list (name + description + parameters) in the system prompt
- Based on goal + current observations, LLM decides which tool to call next
- LLM is NOT given a fixed sequence — it decides dynamically each iteration
- If a tool fails, the failure is returned as an observation and LLM adapts

---

## 7. Current Status

### Fully Completed
- AgentState with full schema and persistence
- BaseTool interface with ABC enforcement
- All 4 tools (detect_duplicates, categorize_files, move_files, safe_delete)
- Tool Registry (manual)
- Executor with all 4 safety gates
- Safety layer (permission guard + dry-run + retry)
- SK Kernel with Groq integration
- Agentic loop (ReAct: Plan → Act → Observe → Update)
- Rich structured observations per tool
- Agent Controller with goal validation
- FastAPI server with all endpoints
- Session persistence to local JSON
- Swagger UI working and tested
- CORS configured for Angular

### Partially Implemented
- Undo system: data exists in session JSON, endpoint not built
- Demo endpoint: route defined, demo workspace not created

### Not Yet Started
- Plugin auto-discovery (Phase 1 Step 2)
- `/api/undo/{session_id}` endpoint (Phase 1 Step 3)
- `planner.py` — empty file (Phase 1 Step 4)
- WebSocket real-time streaming (Phase 2)
- Angular UI (Phase 2)
- GitHub setup + README (Phase 3)
- Hosting on Railway (Phase 3)
- CI/CD with GitHub Actions (Phase 3)

---

## 8. Pending Improvements

### Phase 1 — Backend Refinement
1. ✅ Richer observations (DONE)
2. ⬜ Plugin auto-discovery — auto-load tools from `app/tools/` directory
3. ⬜ Undo endpoint — `/api/undo/{session_id}` reads undo_log, reverses moves
4. ⬜ Planner module — generates initial plan from goal before execution

### Phase 2 — UI
5. ⬜ Angular UI — goal input, results panel, session history, dry-run toggle
6. ⬜ WebSocket streaming — real-time step-by-step log streaming to UI

### Phase 3 — Finalization
7. ⬜ GitHub — clean repo, professional README, architecture diagram
8. ⬜ Hosting — Railway free tier deployment
9. ⬜ CI/CD — GitHub Actions auto-test on push

---

## 9. Constraints

**Do NOT build:**
- RAG (retrieval augmented generation)
- Multi-goal or goal scheduling systems
- Learning or memory across sessions
- Vector databases
- Multi-agent systems
- Complex scaling infrastructure
- Microservices
- Authentication system

**Keep it:**
- Single agent, single goal per session
- Local file system focus
- Modular but not over-engineered
- Clean architecture over feature bloat

---

## 10. Resume Goal

**Target role:** Full Stack Developer building AI-powered applications (SDE-1)

**What this project demonstrates:**
- ReAct agentic loop (modern AI agent design pattern)
- Tool-based architecture with standard interfaces
- Safety-first design (code-level enforcement, not just prompt-level)
- Production-grade API (FastAPI + Pydantic + auto-docs)
- Microsoft Semantic Kernel integration
- Groq/Llama 3.3 as reasoning engine
- Session persistence and audit trail
- Dry-run mode (production thinking)
- Angular frontend (when complete)
- CI/CD and deployment (when complete)

**Interview talking points:**
- Why ReAct loop vs static pipeline
- Why Executor is separate from Orchestrator
- Why safety is enforced in code not prompts
- How SHA-256 hashing works for duplicate detection
- How observations drive LLM decision-making
- Why Groq instead of OpenAI (cost + compatibility)