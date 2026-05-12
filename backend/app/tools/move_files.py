import os
import shutil
from app.tools.base_tool import BaseTool, ToolResult


class MoveFilesTool(BaseTool):

    @property
    def name(self) -> str:
        return "move_files"

    @property
    def description(self) -> str:
        return (
            "Moves files from a source path to a destination folder. "
            "Use when the user wants to organize or relocate files. "
            "Supports dry-run and records moves for undo."
        )

    @property
    def parameters(self) -> dict:
        return {
        "files": {
            "type": "list",
            "required": False,
            "description": "List of full file paths to move"
        },
        "category": {
            "type": "str",
            "required": False,
            "description": "Optional: Category name (e.g. 'Images') to move all files of that type"
        },
        "source_path": {
            "type": "str",
            "required": False,
            "description": "Required if using 'category': The folder to scan for that category"
        },
        "destination": {
            "type": "str",
            "required": True,
            "description": "Full path to the destination folder"
        }
    }

    def run(self, params: dict, dry_run: bool = False) -> ToolResult:
        files = params.get("files", [])
        category = params.get("category")
        source_path = params.get("source_path")
        destination = params.get("destination")
        if category and source_path:
            if not os.path.exists(source_path):
                return ToolResult(success=False, error=f"Source path does not exist: {source_path}")
            
            from app.tools.categorize_files import get_category # Import here to avoid circularity
            for filename in os.listdir(source_path):
                full_p = os.path.join(source_path, filename)
                if os.path.isfile(full_p) and get_category(filename) == category:
                    files.append(full_p.replace("\\", "/"))

        if not files:
            return ToolResult(success=False, error="No files found to move.")

        if not destination:
            return ToolResult(success=False, error="No destination provided.")

        moved = []
        skipped = []
        undo_log = []

        # Create destination folder if it doesn't exist
        if not dry_run:
            os.makedirs(destination, exist_ok=True)

        for filepath in files:
            if not os.path.exists(filepath):
                skipped.append({"file": filepath, "reason": "File not found"})
                continue

            filename = os.path.basename(filepath)
            dest_path = os.path.join(destination, filename)

            # Handle name conflicts — don't overwrite existing files
            if os.path.exists(dest_path):
                skipped.append({"file": filepath, "reason": "File already exists at destination"})
                continue

            if dry_run:
                moved.append({"from": filepath, "to": dest_path, "status": "simulated"})
            else:
                shutil.move(filepath, dest_path)
                moved.append({"from": filepath, "to": dest_path, "status": "moved"})
                # Record for undo — where it came from
                undo_log.append({"from": dest_path, "to": filepath})

        prefix = "[DRY RUN] " if dry_run else ""
        return ToolResult(
            success=True,
            data={
                "moved": moved,
                "skipped": skipped,
                "undo_log": undo_log,
                "total_moved": len(moved),
                "total_skipped": len(skipped),
            },
            message=f"{prefix}Moved {len(moved)} files. Skipped {len(skipped)}."
        )