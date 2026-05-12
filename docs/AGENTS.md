# Archon: AI Agent Instructions

**Archon** is an AI-powered file management agent for Windows that executes natural language goals like "Clean my Downloads folder" autonomously using a ReAct loop with Semantic Kernel + Groq LLM.

## Quick Context

- **Main entry**: [main.py](main.py) (FastAPI server)
- **Architecture**: See [architecture.md](architecture.md) and [project_context.md](project_context.md)
- **Stack**: Python 3.11, FastAPI, Semantic Kernel, Groq (Llama 3.3), WebSocket streaming
- **Design principle**: Dry-run by default (safe-first), all operations reversible

## Core Architecture at a Glance

```
User Goal → Controller → Orchestrator (ReAct loop) → Executor (4-gate safety) → Tools → AgentState
```

| Layer | File(s) | Responsibility |
|-------|---------|-----------------|
| **API** | main.py, routes.py, websocket.py | HTTP/WebSocket endpoints, request validation |
| **Agent** | controller.py, orchestrator.py | Coordination, LLM interaction, ReAct loop |
| **Execution** | executor.py | Tool dispatch, 4-gate safety pipeline, retry logic |
| **State** | state.py | Single source of truth (persisted to `memory/{id}.json`) |
| **Safety** | safety.py | Path validation, blocked folder checks |
| **Tools** | tools/ | File operations (detect_duplicates, categorize_files, move_files, safe_delete) |

## Key Design Patterns

### 1. **State-Driven Architecture**
- `AgentState` is the single source of truth shared across all layers
- Persisted to `memory/{session_id}.json` after every step
- Supports session recovery and inspection

### 2. **ReAct Loop (Plan → Act → Observe → Update)**
- LLM decides next action as JSON with zero temperature
- Executor runs tool through safety gates
- Tool result converted to natural language observation
- Observation fed back to ChatHistory for next iteration (max 10 iterations)

### 3. **Tool System (Auto-Discovery)**
- All tools inherit from `BaseTool` (see [app/tools/base_tool.py](app/tools/base_tool.py))
- Auto-discovered at startup from `app/tools/`
- **Required interface**: `name`, `description`, `parameters`, `run(params, dry_run)`
- Returns `ToolResult(success, data, message, error)`

### 4. **Safety-by-Design**
- **4-gate pipeline** (Executor.run_step):
  1. Tool exists?
  2. Parameters valid per schema?
  3. Paths safe (not in BLOCKED_PATHS)?
  4. Dry-run mode respected?
- **Soft-delete only**: Files moved to `recycle_bin/`, never permanently deleted
- **No prompt-based safety**: Blocking is code-level, not LLM-dependent

### 5. **Dry-Run First**
- Default: `dry_run=true` (no actual changes)
- Tools simulate operations, return predicted results
- User must explicitly enable `dry_run=false` for real changes
- All moves logged for undo

## Quick Start for Development

### Setup
```bash
pip install -r requirements.txt
# Create .env
echo "GROQ_API_KEY=your_key" >> .env
echo "GROQ_MODEL=llama-3.3-70b-versatile" >> .env
```

### Run Server
```bash
python main.py
# Swagger UI: http://localhost:8000/docs
```

### Test (Dry-Run)
```bash
curl -X POST http://localhost:8000/api/run \
  -H "Content-Type: application/json" \
  -d '{"goal": "Find duplicates in C:/Users/HP/Downloads", "dry_run": true}'
```

### Run Tests
```bash
python test_state.py  # Full integration test
```

## Adding a New Tool

1. Create `app/tools/my_tool.py`
2. Inherit from `BaseTool`:
   ```python
   class MyTool(BaseTool):
       @property
       def name(self) -> str:
           return "my_tool"
       
       @property
       def description(self) -> str:
           return "Does something useful"
       
       @property
       def parameters(self) -> dict:
           return {"path": {"type": "string", "description": "File path"}}
       
       def run(self, params: dict, dry_run: bool) -> ToolResult:
           # Your implementation
           return ToolResult(success=True, data=result, message="Done")
   ```
3. Auto-discovered on startup—immediately available to LLM

## Important Conventions

### Path Handling
- Always use forward slashes: `C:/Users/HP/...`
- Normalize with `os.path.normpath()` for comparison
- Extract paths from goals using regex
- Pass exact user-provided paths to LLM (don't modify)

### LLM Communication
- LLM always responds with JSON in exact format:
  ```json
  {"action": "tool_name", "params": {...}, "reasoning": "..."}
  ```
- Parser handles markdown wrapping: `` ```json ... ``` ``
- Fallback: extract first `{…}` if malformed
- Max tokens=500 per call (sufficient for action decisions)

### Observation Building
- Tool results converted to natural language for next LLM call
- Format: "Step X: tool_name found Y. Files: [paths]. Recommend: next_action"
- Tool-specific logic in `Orchestrator.build_observation()`

### Error Handling
- Validation errors → return early with clear message
- Safety errors → block with reason
- Tool errors → retry up to 3 times with exponential backoff (2s, 4s, 6s)
- LLM parsing errors → ask LLM to respond with valid JSON only

## Common Task Checklist

- [ ] **Add a new file operation?** Create new tool in `app/tools/`
- [ ] **Change LLM behavior?** Update system prompt in `Orchestrator.__init__()`
- [ ] **Add API endpoint?** Update `app/api/routes.py`
- [ ] **Modify state tracking?** Update `AgentState` in `app/agent/state.py`
- [ ] **Test a tool?** Write unit test, then test via `python test_state.py`
- [ ] **Debug a session?** Load `memory/{session_id}.json` and inspect observations

## Documentation Links

- **Architecture Details**: [architecture.md](architecture.md) (component diagrams, data flow)
- **Project Context**: [project_context.md](project_context.md) (vision, roadmap, safety philosophy)
- **Code Examples**: See `test_state.py` for full integration flow

## Session Memory (For Agents)

When working on changes:
1. **Understand the flow**: Which layer does your change affect? (API → Controller → Orchestrator → Executor → Tools → State)
2. **Test incrementally**: Use `python test_state.py` or curl to verify behavior
3. **Preserve invariants**:
   - `AgentState` must be persisted after every step
   - Tools must always return `ToolResult` with consistent fields
   - Safety gates in `Executor` must never be bypassed
   - Dry-run mode must be respected by all tools
4. **Logging**: Use logger in context for observability (e.g., `logger.info(f"Step {step_num}: {action}")`)

---

**Yes, this is GitHub Copilot.** Use these guidelines to be immediately productive in Archon. For questions about specific components, refer to the source files—they're well-commented and follow the patterns described here.
