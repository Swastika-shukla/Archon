import os
import shutil
from app.tools.base_tool import BaseTool, ToolResult

CATEGORIES = {
    "Images":     [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico"],
    "Videos":     [".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm"],
    "Audio":      [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma"],
    "Documents":  [".pdf", ".doc", ".docx", ".txt", ".xlsx", ".xls", ".pptx", ".csv", ".rtf"],
    "Archives":   [".zip", ".rar", ".tar", ".gz", ".7z", ".iso", ".dmg"],
    "Code":       [".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".java", ".cpp", ".php"],
    "Executables":[".exe", ".msi", ".bat", ".sh"],
}


def get_category(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    for category, extensions in CATEGORIES.items():
        if ext in extensions:
            return category
    return "Others"


class CategorizeFilesTool(BaseTool):

    @property
    def name(self) -> str:
        return "categorize_files"

    @property
    def description(self) -> str:
        return (
            "Scans a folder and groups files by type into categories like Images, Documents, Videos etc. "
            "Returns category breakdown. "
            "After categorizing, report findings and finish — do not move files unless user explicitly asked to move."
        )

    @property
    def parameters(self) -> dict:
        return {
            "path": {
                "type": "str",
                "required": True,
                "description": "Full path to the folder to categorize"
            }
        }

    def run(self, params: dict, dry_run: bool = False) -> ToolResult:
        path = params.get("path")

        if not os.path.exists(path):
            return ToolResult(success=False, error=f"Path does not exist: {path}")

        try:
            categorized = {}

            for filename in os.listdir(path):
                full_path = os.path.join(path, filename)
                if not os.path.isfile(full_path):
                    continue

                category = get_category(filename)

                if category not in categorized:
                    categorized[category] = []

                categorized[category].append({
                    "filename": filename,
                    "full_path": full_path.replace("\\", "/")
                })

            total_files = sum(len(v) for v in categorized.values())

            moved = []
            skipped = []

            if not dry_run:
                for category, files in categorized.items():
                    category_folder = os.path.join(path, category)
                    os.makedirs(category_folder, exist_ok=True)
                    for file_entry in files:
                        src = file_entry["full_path"]
                        dst = os.path.join(category_folder, file_entry["filename"])
                        if not os.path.exists(dst):
                            shutil.move(src, dst)
                            moved.append(file_entry["filename"])
                        else:
                            skipped.append(file_entry["filename"])

            prefix = "[DRY RUN] " if dry_run else ""
            message = (
                f"{prefix}Categorized {total_files} files into {len(categorized)} categories."
                if dry_run
                else f"Categorized and moved {len(moved)} files into subfolders. Skipped {len(skipped)}."
            )

            return ToolResult(
                success=True,
                data={
                    "categorized": categorized,
                    "total_files": total_files,
                    "categories_found": list(categorized.keys()),
                    "total_moved": len(moved),
                    "total_skipped": len(skipped),
                },
                message=message
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Error: {str(e)}")