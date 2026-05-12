import os
import shutil
import json


def load_session(session_id: str) -> dict:
    """Reads session JSON from memory/."""
    path = os.path.join("memory", f"{session_id}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Session '{session_id}' not found.")
    with open(path) as f:
        return json.load(f)


def extract_undo_logs(session: dict) -> list[dict]:
    """
    Pulls all undo_log entries from every step result.
    Only move_files produces undo_log — other tools are safely ignored.
    """
    undo_entries = []
    results = session.get("results", {})

    for step_id, result in results.items():
        if not isinstance(result, dict):
            continue
        undo_log = result.get("undo_log", [])
        for entry in undo_log:
            if "from" in entry and "to" in entry:
                undo_entries.append({
                    "step_id": step_id,
                    "from": entry["from"],   # current location (destination)
                    "to": entry["to"],       # original location (source)
                })

    return undo_entries


def reverse_moves(undo_entries: list[dict]) -> dict:
    """
    Moves each file from its current location back to its original location.
    Handles missing files safely — skips instead of crashing.
    """
    undone = []
    skipped = []

    for entry in undo_entries:
        src = entry["from"]   # where file is now
        dst = entry["to"]     # where it should go back

        if not os.path.exists(src):
            skipped.append({
                "file": src,
                "reason": "File not found at current location"
            })
            continue

        # Recreate original directory if it no longer exists
        original_dir = os.path.dirname(dst)
        if original_dir:
            os.makedirs(original_dir, exist_ok=True)

        # Don't overwrite if something already exists at the original path
        if os.path.exists(dst):
            skipped.append({
                "file": src,
                "reason": "File already exists at original location"
            })
            continue

        try:
            shutil.move(src, dst)
            undone.append({
                "restored_to": dst,
                "moved_from": src,
                "status": "restored"
            })
        except Exception as e:
            skipped.append({
                "file": src,
                "reason": str(e)
            })

    return {
        "total_undone": len(undone),
        "total_skipped": len(skipped),
        "undone": undone,
        "skipped": skipped,
    }


def run_undo(session_id: str) -> dict:
    """
    Full undo flow for a session.
    Called directly by the API endpoint.
    """
    session = load_session(session_id)

    # Only undo LIVE runs — dry run sessions have nothing to reverse
    if session.get("is_dry_run", True):
        return {
            "session_id": session_id,
            "message": "This was a dry-run session. No real files were moved — nothing to undo.",
            "total_undone": 0,
            "total_skipped": 0,
            "undone": [],
            "skipped": [],
        }

    undo_entries = extract_undo_logs(session)

    if not undo_entries:
        return {
            "session_id": session_id,
            "message": "No undo log found in this session. Nothing to reverse.",
            "total_undone": 0,
            "total_skipped": 0,
            "undone": [],
            "skipped": [],
        }

    result = reverse_moves(undo_entries)

    return {
        "session_id": session_id,
        "message": f"Undo complete. Restored {result['total_undone']} files.",
        **result,
    }