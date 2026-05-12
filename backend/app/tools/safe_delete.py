import os
import shutil
from datetime import datetime
from app.tools.base_tool import BaseTool, ToolResult

RECYCLE_BIN = "recycle_bin"


class SafeDeleteTool(BaseTool):

    @property
    def name(self) -> str:
        return "safe_delete"

    @property
    def description(self) -> str:
        return (
            "Safely deletes files by moving them to a recycle bin folder. "
            "Files are NOT permanently deleted — they can be recovered. "
            "Use when the user wants to delete duplicate or unwanted files."
        )

    @property
    def parameters(self) -> dict:
        return {
            "files": {
                "type": "list",
                "required": False,
                "description": "List of full file paths to delete"
            },
            "all_duplicates_in": {
                "type": "str",
                "required": False,
                "description": "Optional: Full path to a folder to delete ALL detected duplicates within it"
            }
        }

    def run(self, params: dict, dry_run: bool = False) -> ToolResult:
        files = params.get("files", [])
        all_duplicates_in = params.get("all_duplicates_in")
        if all_duplicates_in:
            from app.tools.detect_duplicates import DetectDuplicatesTool
            dup_tool = DetectDuplicatesTool()
            # Re-run detection to get the list (since we don't have a shared cache yet)
            dup_res = dup_tool.run({"path": all_duplicates_in}, dry_run=False)
            if dup_res.success:
                for group in dup_res.data.get("duplicates", []):
                    files.extend(group.get("remove", []))

        if not files:
            return ToolResult(success=False, error="No files provided or no duplicates found.")

        if not files:
            return ToolResult(success=False, error="No files provided.")

        deleted = []
        skipped = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if not dry_run:
            os.makedirs(RECYCLE_BIN, exist_ok=True)

        for filepath in files:
            if not os.path.exists(filepath):
                skipped.append({"file": filepath, "reason": "File not found"})
                continue

            filename = os.path.basename(filepath)
            # Add timestamp to avoid name conflicts in recycle bin
            bin_filename = f"{timestamp}_{filename}"
            bin_path = os.path.join(RECYCLE_BIN, bin_filename)

            if dry_run:
                deleted.append({
                    "original": filepath,
                    "bin_path": bin_path,
                    "status": "simulated"
                })
            else:
                shutil.move(filepath, bin_path)
                deleted.append({
                    "original": filepath,
                    "bin_path": bin_path,
                    "status": "moved_to_bin"
                })

        prefix = "[DRY RUN] " if dry_run else ""
        undo_log = [
            {"from": entry["bin_path"], "to": entry["original"]}
            for entry in deleted
        ]

        return ToolResult(
            success=True,
            data={
                "deleted": deleted,
                "skipped": skipped,
                "recycle_bin": RECYCLE_BIN,
                "total_deleted": len(deleted),
                "total_skipped": len(skipped),
                "undo_log": undo_log,
            },
            message=f"{prefix}Safely deleted {len(deleted)} files. Skipped {len(skipped)}."
        )