import os
import json
import shutil
from app.tools.base_tool import BaseTool, ToolResult


class UndoSessionTool(BaseTool):

    @property
    def name(self) -> str:
        return "undo_session"

    @property
    def description(self) -> str:
        return (
            "Reverses file moves from a previous session using its session ID. "
            "Use when user wants to undo or reverse a previous run. "
            "Input: session_id string."
        )

    @property
    def parameters(self) -> dict:
        return {
            "session_id": {
                "type": "str",
                "required": True,
                "description": "The session ID to undo"
            }
        }

    def run(self, params: dict, dry_run: bool = False) -> ToolResult:
        session_id = params.get("session_id", "").strip()

        if not session_id:
            return ToolResult(success=False, error="No session_id provided.")

        path = os.path.join("memory", f"{session_id}.json")

        if not os.path.exists(path):
            return ToolResult(
                success=False,
                error=f"Invalid session ID '{session_id}'. No session found with this ID. Please check the session ID from your history panel and try again."
            )

        with open(path) as f:
            session = json.load(f)

        if session.get("is_dry_run", True):
            return ToolResult(
                success=True,
                data={"undone": 0, "skipped": 0},
                message="This was a dry-run session. Nothing to undo."
            )

        undo_entries = []
        for step_id, result in session.get("results", {}).items():
            if not isinstance(result, dict):
                continue
            for entry in result.get("undo_log", []):
                if "from" in entry and "to" in entry:
                    undo_entries.append(entry)

        if not undo_entries:
            return ToolResult(
                success=True,
                data={"undone": 0, "skipped": 0},
                message="No undo log found in this session."
            )

        undone = []
        skipped = []

        for entry in undo_entries:
            src = entry["from"]
            dst = entry["to"]

            if not os.path.exists(src):
                skipped.append(src)
                continue

            os.makedirs(os.path.dirname(dst), exist_ok=True)

            if os.path.exists(dst):
                skipped.append(src)
                continue

            if not dry_run:
                shutil.move(src, dst)

            undone.append(os.path.basename(dst))

        return ToolResult(
            success=True,
            data={
                "undone": len(undone),
                "skipped": len(skipped),
                "files": undone[:5]
            },
            message=f"Restored {len(undone)} files. Skipped {len(skipped)}."
        )

