import os
from app.tools.base_tool import BaseTool, ToolResult


class FindFileByNameTool(BaseTool):

    @property
    def name(self) -> str:
        return "find_file_by_name"

    @property
    def description(self) -> str:
        return (
            "Finds a file by name across Desktop, Downloads, and Documents. "
            "Returns matching file paths. "
            "Use only for finding files — do not suggest any further actions after finding."
        )

    @property
    def parameters(self) -> dict:
        return {
            "name": {
                "type": "str",
                "required": True
            }
        }

    def run(self, params: dict, dry_run: bool = False) -> ToolResult:
        name = params.get("name", "").lower().strip()

        if not name:
            return ToolResult(success=False, error="No filename provided.")

        from app.agent.orchestrator import get_user_folders
        home, downloads, documents, desktop = get_user_folders()
        search_dirs = [
            desktop,
            downloads,
            documents,
        ]

        matches = []

        for folder in search_dirs:
            if not os.path.exists(folder):
                continue
            try:
                for entry in os.scandir(folder):
                    if entry.is_file() and name in entry.name.lower():
                        matches.append(entry.path.replace("\\", "/"))
                    if len(matches) >= 5:
                        break
            except PermissionError:
                continue

        if matches:
            return ToolResult(
                success=True,
                data={
                    "found": True,
                    "matches": matches,
                    "total_found": len(matches),
                },
                message=f"Found {len(matches)} file(s) matching '{name}'."
            )

        return ToolResult(
            success=True,
            data={"found": False},
            message=f"No files matching '{name}' found."
        )
