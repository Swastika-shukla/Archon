# ARCHITECTURE.md
> Technical architecture reference for Archon
> Last updated: April 2026

---

## 1. High-Level Architecture

```
USER
  │
  │  natural language goal
  ▼
┌─────────────────────────────────────────────────────────┐
│                    ANGULAR UI (pending)                  │
│         Goal input · Results panel · Live logs          │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP POST /api/run
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   FASTAPI SERVER                         │
│              Routes · Pydantic validation                │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                 AGENT CONTROLLER                         │
│         Goal validation · AgentState creation           │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│              ORCHESTRATOR (ReAct Loop)                   │
│                                                          │
│   ┌──────────┐   ┌────────┐   ┌─────────┐   ┌───────┐  │
│   │  PLAN    │ → │  ACT   │ → │ OBSERVE │ → │UPDATE │  │
│   │ ask LLM  │   │ execute│   │ build   │   │ feed  │  │
│   │ what     │   │ via    │   │ rich    │   │ back  │  │
│   │ next?    │   │executor│   │ summary │   │ to LLM│  │
│   └──────────┘   └────────┘   └─────────┘   └───────┘  │
│         ▲                                        │       │
│         └────────────────────────────────────────┘       │
└──────┬─────────────────────────┬───────────────────────-─┘
       │                         │
       ▼                         ▼
┌─────────────┐         ┌────────────────┐
│ SK KERNEL   │         │   EXECUTOR     │
│ Groq/Llama  │         │ 4-gate safety  │
│ ChatHistory │         │ + retry logic  │
└─────────────┘         └───────┬────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │     TOOL REGISTRY     │
                    │  detect_duplicates    │
                    │  categorize_files     │
                    │  move_files           │
                    │  safe_delete          │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  SAFETY LAYER         │
                    │  permission guard     │
                    │  dry-run enforcement  │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   LOCAL FILESYSTEM    │
                    │  C:/Users/HP/...      │
                    └───────────────────────┘
                                │
                    ┌───────────────────────┐
                    │   MEMORY (local JSON) │
                    │  memory/{session}.json│
                    └───────────────────────┘
```

---

## 2. Component Breakdown

### FastAPI Server (`main.py` + `app/api/routes.py`)
**Responsibility:**
- Receive HTTP requests from UI or Swagger
- Validate request shape via Pydantic
- Route to correct handler function
- Return JSON responses

**Interacts with:**
- Agent Controller (passes goal + dry_run)
- Memory folder (reads session JSON for `/status` endpoint)

**Endpoints:**
```
POST   /api/run                → runs agent
GET    /api/status/{id}        → retrieve session
GET    /api/sessions           → list all sessions
DELETE /api/session/{id}       → delete session
GET    /api/tools              → list tools
GET    /api/health             → health check
```

---

### Agent Controller (`app/agent/controller.py`)
**Responsibility:**
- First layer of business logic after API
- Validates goal (not empty, 10–500 chars)
- Creates fresh AgentState
- Starts Orchestrator
- Returns final state to API

**Interacts with:**
- FastAPI routes (receives call from)
- AgentState (creates)
- Orchestrator (calls run())

**Why it exists:**
Separates API concerns from agent concerns. API doesn't know about AgentState. Orchestrator doesn't know about HTTP.

---

### Orchestrator (`app/agent/orchestrator.py`)
**Responsibility:**
- Runs the ReAct agentic loop
- Manages ChatHistory across all iterations
- Communicates with LLM via SK Kernel
- Parses LLM JSON responses
- Creates TaskSteps from LLM decisions
- Builds rich observations from tool results
- Updates AgentState after every iteration

**Interacts with:**
- SK Kernel (sends ChatHistory, receives LLM decision)
- Executor (dispatches TaskStep for execution)
- AgentState (reads + updates throughout loop)
- Tool Registry (calls `list_tools()` for system prompt)

**Key functions:**
- `build_system_prompt()` — builds LLM instructions with tool list + OS context
- `parse_llm_response()` — safely parses JSON from LLM (handles markdown wrapping)
- `build_observation()` — creates structured per-tool summaries
- `run()` — async main loop

---

### SK Kernel (`app/agent/kernel.py`)
**Responsibility:**
- Configure Semantic Kernel to use Groq as LLM backend
- Create AsyncOpenAI client pointed at Groq's URL
- Register OpenAIChatCompletion service
- Return configured kernel instance

**Why Groq works with SK's OpenAI connector:**
Groq implements the exact same HTTP API format as OpenAI. SK sends OpenAI-format requests. Groq receives and understands them. Response format is identical. SK never knows it's not talking to OpenAI.

**Config:**
```python
base_url = "https://api.groq.com/openai/v1"
model    = "llama-3.3-70b-versatile"
temp     = 0.1   # near-deterministic for JSON consistency
tokens   = 500   # sufficient for JSON action decisions
```

---

### Executor (`app/core/executor.py`)
**Responsibility:**
- Single point of tool execution — nothing bypasses this
- Runs 4 sequential safety gates before every tool call
- Handles dry-run routing
- Implements retry with exponential backoff
- Updates AgentState after execution

**4 Gates (in order):**
```
Gate 1: Tool exists in TOOL_REGISTRY?
Gate 2: All required params present? (via tool.validate_params())
Gate 3: All paths safe? (via check_params_safety())
Gate 4: Dry-run mode? → route to simulation path
```

**Retry logic:**
```
Attempt 1 → fail → wait 2s
Attempt 2 → fail → wait 4s
Attempt 3 → fail → mark step failed, return error
```

**Interacts with:**
- Tool Registry (calls `get_tool()`)
- Safety module (calls `check_params_safety()`)
- Each tool (calls `tool.run()`)
- AgentState (calls `mark_step_done()` or `mark_step_failed()`)

---

### Safety Module (`app/core/safety.py`)
**Responsibility:**
- Define blocked system paths
- Normalize and compare paths
- Extract path-like values from any params dict
- Return (is_safe, error_message) tuples

**Blocked paths:**
```
C:/Windows
C:/Program Files
C:/Program Files (x86)
C:/ProgramData
~/.ssh
~/AppData/Roaming
~/AppData/Local/Microsoft
```

**Why code-level and not prompt-level:**
During development, the LLM was instructed in the system prompt to never touch system folders. It ignored this and attempted `C:/Windows/System32`. Code-level enforcement is guaranteed. Prompt-level is a suggestion.

---

### Tool Registry (`app/tools/__init__.py`)
**Responsibility:**
- Map tool name strings to tool instances
- Expose `get_tool(name)` for Executor
- Expose `list_tools()` for system prompt and `/api/tools`

**Current implementation:** Manual registration dict
**Pending:** Auto-discovery via `importlib` + `inspect`

---

### AgentState (`app/agent/state.py`)
**Responsibility:**
- Single source of truth for one agent session
- Shared across Controller → Orchestrator → Executor
- Persisted to disk after every step

**Full schema:**
```python
@dataclass
class AgentState:
    session_id: str          # UUID, unique per run
    goal: str                # original user goal, immutable
    status: AgentStatus      # PENDING|RUNNING|COMPLETED|FAILED
    is_dry_run: bool         # True = simulate only
    plan: list[TaskStep]     # steps created during execution
    completed_steps: list[str]  # IDs of finished steps
    results: dict            # step_id → tool output data
    observations: list[str]  # structured summaries fed to LLM
    created_at: str          # ISO timestamp
    updated_at: str          # updated on every change

@dataclass
class TaskStep:
    id: str         # "step_1", "step_2" etc
    tool: str       # tool name string
    params: dict    # params passed to tool
    status: str     # pending|running|done|failed
    result: Any     # tool output after execution
    error: str      # error message if failed
```

---

## 3. Execution Flow — Step by Step

```
1. HTTP POST /api/run arrives at FastAPI
   Body: {"goal": "Clean Downloads", "dry_run": true}

2. Pydantic validates RunRequest shape
   → goal: str present ✓
   → dry_run: bool present ✓

3. run_agent() calls AgentController.run()

4. Controller validates goal
   → not empty ✓
   → length 10–500 chars ✓

5. Controller creates AgentState
   session_id = new UUID
   goal = "Clean Downloads"
   is_dry_run = True
   status = PENDING

6. Controller calls Orchestrator.run(state)

7. Orchestrator initializes:
   → builds system prompt (tool list + OS + rules)
   → creates ChatHistory
   → adds system message
   → adds user message with goal

8. LOOP ITERATION 1:
   a. PLAN: sends ChatHistory to Groq via SK Kernel
      → SK builds OpenAI-format HTTP request
      → sends to https://api.groq.com/openai/v1/chat/completions
      → Llama 3.3 reads tools + goal
      → responds: {"action": "detect_duplicates", "params": {...}}

   b. Parse response → action="detect_duplicates", params={path:...}

   c. Create TaskStep(id="step_1", tool="detect_duplicates", params={...})
      Append to state.plan

   d. ACT: call executor.run_step(step_1, state)
      Gate 1: get_tool("detect_duplicates") → found ✓
      Gate 2: validate_params({"path": "..."}) → path present ✓
      Gate 3: check_params_safety({"path": "..."}) → not system folder ✓
      Gate 4: is_dry_run=True → call tool.run(dry_run=True)
      Tool runs → returns ToolResult(success=True, data={...}, message="...")

   e. OBSERVE: build_observation("detect_duplicates", data, message, 1)
      → "Step 1: detect_duplicates scanned 1333 files.
          Found 94 duplicates across 47 groups.
          Recommended: safe_delete on duplicates."

   f. UPDATE:
      state.mark_step_done("step_1", result.data)
      state.add_observation(observation)
      state.save() → writes memory/{session_id}.json
      chat_history.add_assistant_message(llm_response)
      chat_history.add_user_message("Observation: ... What next?")

9. LOOP ITERATION 2: (same cycle, LLM sees observation from step 1)
   LLM decides: categorize_files
   Same gates → tool runs → observation built → state updated

10. LOOP ITERATION 3:
    LLM sees both observations, decides goal is complete
    Returns: {"action": "finish", "reasoning": "Done."}
    state.status = COMPLETED
    state.save()
    Loop exits

11. Orchestrator returns final state to Controller
    Controller returns state to routes.py

12. routes.py builds RunResponse from state
    Returns HTTP 200 JSON to caller
```

---

## 4. Agent Loop — Detailed Breakdown

### PLAN Phase
```
Input:  full ChatHistory (system prompt + goal + all previous observations)
Action: send to Groq via SK, receive JSON decision
Output: {action: string, params: dict, reasoning: string}

What LLM sees:
  - complete tool catalog with descriptions + parameter schemas
  - original goal (never changes)
  - every observation from previous iterations
  - rules: JSON only, no system folders, no recursive by default

Temperature 0.1 → near-deterministic → consistent JSON format
```

### ACT Phase
```
Input:  action name + params from LLM
Action: create TaskStep → pass through Executor's 4 gates → run tool
Output: ToolResult(success, data, message, error)

If gate fails: step marked failed immediately, no retry
If tool fails: retry up to 3 times with exponential backoff
```

### OBSERVE Phase
```
Input:  ToolResult data + tool name + step number
Action: build_observation() generates structured summary per tool
Output: rich string with counts, insights, recommended next action

Per-tool observation templates:
  detect_duplicates → file count, duplicate count, top duplicate, recommendation
  categorize_files  → category breakdown with counts, recommendation
  move_files        → moved count, skipped count, undo log count
  safe_delete       → deleted count, skipped count, bin location
```

### UPDATE Phase
```
Input:  observation string
Action:
  1. state.mark_step_done() or mark_step_failed()
  2. state.add_observation(observation)
  3. state.save() → disk write
  4. chat_history.add_assistant_message(llm_response)
  5. chat_history.add_user_message("Observation: {obs}. What next?")
Output: updated ChatHistory ready for next PLAN phase

Key insight: observation goes into ChatHistory as a USER message.
The LLM reads it as external feedback, enabling true reasoning adaptation.
```

---

## 5. Tool System Design

### Interface (`app/tools/base_tool.py`)
```python
class BaseTool(ABC):
    @property @abstractmethod
    def name(self) -> str: ...          # unique identifier

    @property @abstractmethod
    def description(self) -> str: ...   # sent to LLM in system prompt

    @property @abstractmethod
    def parameters(self) -> dict: ...   # schema for Executor validation

    @abstractmethod
    def run(self, params: dict, dry_run: bool = False) -> ToolResult: ...

    def validate_params(self, params: dict) -> tuple[bool, str]: ...
    # built-in: checks required params are present
```

`ABC` (Abstract Base Class) enforcement means Python throws an error at import time if a tool is missing any required method. Bugs caught before runtime.

### ToolResult (`app/tools/base_tool.py`)
```python
@dataclass
class ToolResult:
    success: bool    # did it work?
    data: Any        # structured output (dict)
    message: str     # human-readable summary
    error: str       # error message if success=False
```

Every tool returns exactly this shape. Executor handles it uniformly regardless of which tool ran.

### Registry (`app/tools/__init__.py`)
```python
TOOL_REGISTRY = {
    "detect_duplicates": DetectDuplicatesTool(),
    "move_files":        MoveFilesTool(),
    "categorize_files":  CategorizeFilesTool(),
    "safe_delete":       SafeDeleteTool(),
}

def get_tool(name: str) → BaseTool | None
def list_tools() → list[dict]  # name + description + parameters
```

### Execution Flow
```
LLM decides: "detect_duplicates" with params {"path": "C:/Downloads"}
    ↓
Orchestrator: get_tool("detect_duplicates") → DetectDuplicatesTool instance
    ↓
Executor: validate_params({"path": "..."}) → True
    ↓
Executor: check_params_safety({"path": "..."}) → True
    ↓
Executor: tool.run({"path": "..."}, dry_run=True)
    ↓
DetectDuplicatesTool.run() executes
    ↓
Returns ToolResult
    ↓
Executor updates AgentState
    ↓
Orchestrator builds observation from ToolResult.data
```

---

## 6. Safety Layer Design

### Where Safety Is Enforced

```
Layer 1: API (FastAPI + Pydantic)
  → Rejects malformed requests automatically
  → Wrong types, missing fields → 422 before code runs

Layer 2: Controller
  → Goal too short/long/empty → rejected before agent starts

Layer 3: Executor Gate 1
  → Tool name not in registry → rejected, never runs

Layer 4: Executor Gate 2
  → Required params missing → rejected, never runs

Layer 5: Executor Gate 3 (safety.py)
  → Path in blocked list → rejected, never runs
  → Applies to ALL path-like params in the request

Layer 6: Executor Gate 4
  → dry_run=True → tool runs in simulation mode, zero disk writes

Layer 7: Tool Level
  → Each tool has internal existence checks (file not found, not a dir)
  → Handles name conflicts in move_files (won't overwrite)
  → safe_delete never calls os.remove() — always shutil.move() to bin

Layer 8: Retry
  → Transient failures retried up to 3 times
  → Permanent failures propagated as observations to LLM
```

### Why Code-Level, Not Prompt-Level
LLMs are non-deterministic. Even with explicit instructions, they can deviate. During development, the LLM attempted `C:/Windows/System32` despite being told not to. The Executor's Gate 3 blocked it. Code guarantees. Prompts suggest.

---

## 7. State Management

### What AgentState Stores
```
session_id      → unique identifier for this run
goal            → original user input, never modified
status          → current phase (PENDING/RUNNING/COMPLETED/FAILED)
is_dry_run      → simulation flag, set once at creation
plan            → list of TaskStep objects created during execution
completed_steps → list of step IDs that finished successfully
results         → dict mapping step_id to tool output data
observations    → list of rich text summaries fed back to LLM
created_at      → session start timestamp
updated_at      → last modification timestamp
```

### How It's Updated
```
After Executor runs a step:
  mark_step_done(step_id, result_data)
    → step.status = "done"
    → completed_steps.append(step_id)
    → results[step_id] = result_data
    → updated_at = now()

After observation built:
  add_observation(observation_string)
    → observations.append(obs)
    → updated_at = now()

After every update:
  state.save()
    → writes memory/{session_id}.json
    → full state serialized to disk
```

### Persistence
- Location: `memory/{session_id}.json`
- Format: JSON, human-readable
- Timing: written after every step (not just at end)
- Purpose: audit trail, crash recovery, API retrieval, undo support
- Excluded from git: `memory/` in `.gitignore`

---

## 8. Data Flow

```
HTTP Request Body:
  {"goal": "Clean Downloads", "dry_run": true}
    ↓
RunRequest (Pydantic model) — validated
    ↓
AgentController.run(goal, dry_run)
    ↓
AgentState created:
  {session_id, goal, is_dry_run, status=PENDING, plan=[], ...}
    ↓
Orchestrator.run(state)
  ↓
  System prompt (JSON string) → ChatHistory
  goal string → ChatHistory
  ↓
  ChatHistory → SK Kernel → HTTP request → Groq
  ↓
  Groq response (JSON string) → parse_llm_response() → dict
  {action: "detect_duplicates", params: {path: "..."}, reasoning: "..."}
  ↓
  TaskStep created → state.plan.append(step)
  ↓
  TaskStep → Executor.run_step(step, state)
  ↓
  ToolResult ← tool.run(params, dry_run)
  {success: True, data: {total_files: 1333, ...}, message: "..."}
  ↓
  observation string ← build_observation(tool_name, data, message, step)
  "Step 1: detect_duplicates scanned 1333 files. Found 94 duplicates..."
  ↓
  state updated: completed_steps, results, observations
  state.save() → memory/{session_id}.json
  ↓
  observation → ChatHistory (as user message)
  ↓
  [loop repeats]
  ↓
RunResponse built from final state:
  {session_id, status, steps_run, observations, dry_run}
    ↓
HTTP 200 JSON response
```

---

## 9. Design Decisions

### Why ReAct Loop Instead of Static Pipeline?

A static pipeline would be:
```
Step 1: always detect_duplicates
Step 2: always categorize_files
Step 3: always safe_delete
```

Problems:
- Cannot adapt if step 1 finds nothing
- Cannot handle different goals differently
- Cannot recover from failures intelligently

ReAct loop:
- LLM re-reasons after every step using observations
- Can skip steps that aren't needed
- Can retry with different params if tool fails
- Can handle any goal, not just the pre-programmed ones
- This is the difference between automation and intelligence

### Why Tool-Based Architecture?

Alternative: put all file logic in one big script.

Problems:
- Cannot add new capabilities without touching existing code
- Cannot test individual operations in isolation
- Cannot reuse tools across different goals

Tool-based architecture:
- Each tool is independently testable
- New tool = new file + one registry line
- Tools have no knowledge of each other
- LLM can combine tools in any order

### Why Executor Is Separate from Orchestrator?

Without Executor:
- Safety checks would be copy-pasted into every tool
- Orchestrator would be 500+ lines
- Adding a new safety rule requires modifying every tool

With Executor:
- One place for all safety logic
- Orchestrator only decides what to run
- Executor decides how to run it safely
- Adding safety rule = one change in one file

### Why Safety in Code and Not in Prompts?

Prompts are suggestions. LLMs are non-deterministic. During development:
- System prompt said: "never operate on C:/Windows"
- LLM still returned: `{"action": "detect_duplicates", "params": {"path": "C:/Windows/System32"}}`
- Executor Gate 3 caught it and blocked execution

If safety was only in the prompt: the tool would have run on System32.
Code-level safety is the only reliable safety.

### Why Groq Instead of OpenAI?

- OpenAI costs money (pay per token)
- Groq is free tier, no credit card
- Groq uses identical API format as OpenAI
- SK's OpenAI connector works with Groq via URL swap
- Llama 3.3 70B is capable enough for JSON tool decisions
- Groq's LPU hardware makes it faster than OpenAI for inference

### Why Local JSON Storage Instead of Database?

- Archon is a local tool — no server needed
- JSON files are human-readable (easy to debug)
- No setup required (no PostgreSQL, no MongoDB)
- Simple enough for the use case
- Sufficient for session persistence and undo logs
- Can be upgraded to SQLite or Supabase later if needed

### Why Dry-Run as Default?

File operations are destructive and irreversible in most systems. Making dry-run the default means:
- Accidental runs are always safe
- Users can preview before committing
- Development and testing never touch real files
- User must explicitly opt-in to real changes

---

## 10. Extensibility

### Adding a New Tool

1. Create `app/tools/your_tool.py`
2. Inherit from `BaseTool`
3. Implement: `name`, `description`, `parameters`, `run()`
4. Add to `TOOL_REGISTRY` in `app/tools/__init__.py`
5. Done — the LLM will see it in the next run's system prompt

Example:
```python
class FindLargeFilesTool(BaseTool):
    @property
    def name(self): return "find_large_files"
    @property
    def description(self): return "Finds files larger than a given size threshold."
    @property
    def parameters(self):
        return {
            "path": {"type": "str", "required": True},
            "min_size_mb": {"type": "int", "required": False}
        }
    def run(self, params, dry_run=False):
        # implementation
        return ToolResult(success=True, data={...}, message="...")
```

### Pending: Auto-Discovery
When implemented, adding a tool will require ZERO changes to `__init__.py`. Just drop the file in `app/tools/` and it registers itself at startup.

### Adding a New API Endpoint
Add a route function to `app/api/routes.py`. No other files change.

### Switching LLMs
Change `kernel.py` only:
- Point `base_url` at different provider
- Change `ai_model_id`
- Everything else stays identical

### Adding New Safety Rules
Add blocked paths to `BLOCKED_PATHS` list in `app/core/safety.py`. One line. No other files change.

### Future Growth Path
```
Current:   local tool, single user, JSON storage
Phase 2:   Angular UI, WebSocket streaming
Phase 3:   hosted backend, demo workspace
Future:    multi-user sessions, database storage,
           additional tools, mobile UI
           (none of this required for resume)
```