import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.agent.state import AgentState
from app.agent.orchestrator import Orchestrator

ws_router = APIRouter()


@ws_router.websocket("/ws/run")
async def websocket_run(websocket: WebSocket):
    await websocket.accept()

    # Connection confirmation
    await websocket.send_json(
        {
            "type": "connected",
            "step": 0,
            "data": {"message": "WebSocket connection established"},
        }
    )

    try:
        raw = await websocket.receive_text()

        # Safe JSON parsing
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            await websocket.send_json(
                {
                    "type": "error",
                    "step": 0,
                    "data": {"message": "Invalid JSON payload"},
                }
            )
            return

        goal = payload.get("goal", "").strip()
        dry_run = payload.get("dry_run", True)

        if not goal :
            await websocket.send_json(
                {
                    "type": "error",
                    "step": 0,
                    "data": {"message": "Please type something to get started."},
                }
            )
            return

        # Start event
        await websocket.send_json(
            {"type": "start", "step": 0, "data": {"goal": goal, "dry_run": dry_run}}
        )

        state = AgentState(goal=goal, is_dry_run=dry_run)
        orchestrator = Orchestrator()

        # Run agent with streaming
        await orchestrator.run(state, websocket=websocket)

        # Final fallback completion event
        await websocket.send_json(
            {
                "type": "complete",
                "step": len(state.plan),
                "data": {"status": state.status.value},
            }
        )

    except WebSocketDisconnect:
        print("Client disconnected")

    except Exception as e:
        try:
            await websocket.send_json(
                {"type": "error", "step": 0, "data": {"message": str(e)}}
            )
        except Exception:
            pass

    finally:
        try:
            if websocket.client_state.name != "DISCONNECTED":
                await websocket.close()
        except Exception:
            pass
