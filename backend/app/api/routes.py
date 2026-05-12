from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.agent.controller import AgentController
from fastapi import APIRouter, HTTPException
import os
import json

   
router = APIRouter()
controller = AgentController()


# ── Request/Response Models ───────────────────────────────────────────
class PlanRequest(BaseModel):
    goal: str
 

class RunRequest(BaseModel):
    goal: str
    dry_run: bool = True


class RunResponse(BaseModel):
    session_id: str
    status: str
    steps_run: int
    observations: list[str]
    dry_run: bool


# ── Endpoints ─────────────────────────────────────────────────────────

@router.post("/run", response_model=RunResponse)
async def run_agent(request: RunRequest):
    """
    Main endpoint. Accepts a goal and runs the full agentic loop.
    dry_run=True by default — safe for testing.
    """
    try:
        state = await controller.run(
            goal=request.goal,
            dry_run=request.dry_run
        )
        return RunResponse(
            session_id=state.session_id,
            status=state.status.value,
            steps_run=len(state.plan),
            observations=state.observations,
            dry_run=state.is_dry_run,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{session_id}")
async def get_status(session_id: str):
    """
    Returns saved state for a session from memory/ folder.
    """
    path = os.path.join("memory", f"{session_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Session not found.")
    with open(path) as f:
        return JSONResponse(content=json.load(f))


@router.get("/sessions")
async def list_sessions():
    """Lists all past sessions."""
    memory_dir = "memory"
    if not os.path.exists(memory_dir):
        return {"sessions": []}
    files = [f.replace(".json", "") for f in os.listdir(memory_dir) if f.endswith(".json")]
    return {"sessions": files}


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Deletes a session from memory."""
    path = os.path.join("memory", f"{session_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Session not found.")
    os.remove(path)
    return {"message": f"Session {session_id} deleted."}


@router.get("/tools")
async def list_tools():
    """Returns all available tools — useful for UI and debugging."""
    from app.tools import list_tools as get_tools
    return {"tools": get_tools()}


@router.get("/health")
async def health():
    """Quick health check endpoint."""
    return {"status": "ok", "agent": "Archon"}

    
@router.post("/plan")
async def generate_plan(request: PlanRequest):
    from app.agent.planner import Planner

    if not request.goal or not request.goal.strip():
        raise HTTPException(status_code=400, detail="Goal cannot be empty.")
    if len(request.goal.strip()) < 10:
        raise HTTPException(status_code=400, detail="Goal is too short. Please be more specific.")
    if len(request.goal) > 500:
        raise HTTPException(status_code=400, detail="Goal is too long. Keep it under 500 characters.")

    try:
        planner = Planner()
        plan = await planner.generate(goal=request.goal.strip())
        return {"goal": request.goal.strip(), "steps": len(plan), "plan": plan}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/undo/{session_id}")
def undo_session(session_id: str):
    """
    Reverses all move_files operations from a session.
    Reads the undo_log and moves files back to original locations.
    """
    from app.core.undo import run_undo

    try:
        result = run_undo(session_id)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))