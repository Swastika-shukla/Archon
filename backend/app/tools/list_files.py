import os
from app.tools.base_tool import BaseTool, ToolResult


class ListFilesTool(BaseTool):

    @property
    def name(self) -> str:
        return "list_files"

    @property
    def description(self) -> str:
        return (
            "Lists all files in a folder with their full paths. "
            "Use this FIRST before moving or deleting files, "
            "so you know exactly what files exist at that location."
        )

    @property
    def parameters(self) -> dict:
        return {
            "path": {
                "type": "str",
                "required": True,
                "description": "Full path to the folder to list"
            }
        }

    def run(self, params: dict, dry_run: bool = False) -> ToolResult:
        path = params.get("path")

        if not path:
            return ToolResult(success=False, error="No path provided.")

        if not os.path.exists(path):
            return ToolResult(success=False, error=f"Folder not found: {path}")

        if not os.path.isdir(path):
            return ToolResult(success=False, error=f"Path is not a folder: {path}")

        all_files = [
            entry.name
            for entry in os.scandir(path)
            if entry.is_file()
    ]
        total = len(all_files)
        sample = all_files[:5]   # only first 5 files
        return ToolResult(
            success=True,
            data={
                    "path": path,
                    "total_files": total,
                    "sample_files": sample
    },
    message=f"Found {total} files"
)