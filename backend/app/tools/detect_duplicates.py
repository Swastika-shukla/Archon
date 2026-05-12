import os
import hashlib
from collections import defaultdict
from app.tools.base_tool import BaseTool, ToolResult


class DetectDuplicatesTool(BaseTool):

    @property
    def name(self) -> str:
        return "detect_duplicates"

    @property
    def description(self) -> str:
        return (
            "Scans a folder and finds duplicate files based on content hash. "
            "Returns duplicate count and sample file names. "
            "Only use when the user explicitly asks to find or remove duplicates. "
            "After scanning, report findings and finish — do not delete unless user explicitly asked to delete."
        )

    @property
    def parameters(self) -> dict:
        return {
            "path": {
                "type": "str",
                "required": True,
                "description": "Full path to the folder to scan"
            },
            "recursive": {
                "type": "bool",
                "required": False,
                "description": "Scan subfolders too. Defaults to False."
            }
        }

    def _hash_file(self, filepath: str) -> str:
        """
        Reads file in 8KB chunks and generates SHA-256 fingerprint.
        Chunked reading means even 10GB files won't crash your RAM.
        """
        hasher = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except (PermissionError, OSError):
            return None

    def _get_all_files(self, path: str, recursive: bool) -> list[str]:
        files = []
        if recursive:
            for root, _, filenames in os.walk(path):
                for filename in filenames:
                    files.append(os.path.join(root, filename))
        else:
            for filename in os.listdir(path):
                full_path = os.path.join(path, filename)
                if os.path.isfile(full_path):
                    files.append(full_path)
        return files

    def run(self, params: dict, dry_run: bool = False) -> ToolResult:
        path = params.get("path")
        # Force non-recursive in dry_run — keeps simulation fast
        recursive = False if dry_run else params.get("recursive", False)

        if not os.path.exists(path):
            return ToolResult(success=False, error=f"Path does not exist: {path}")

        if not os.path.isdir(path):
            return ToolResult(success=False, error=f"Not a folder: {path}")

        try:
            files = self._get_all_files(path, recursive)
            total = len(files)

            if not files:
                return ToolResult(
                    success=True,
                    data={"duplicates": [], "total_files": 0},
                    message="No files found in the folder."
                )

            
            # STEP 1: Group files by size (fast operation)
            size_map = defaultdict(list)

            for filepath in files:
                try:
                    size = os.path.getsize(filepath)
                    size_map[size].append(filepath)
                except OSError:
                    continue  # skip unreadable files


            # STEP 2: Only hash files that have SAME size (possible duplicates)
            hash_map = defaultdict(list)

            for size, paths in size_map.items():
                if len(paths) < 2:
                    continue  # skip unique size → cannot be duplicates

                for filepath in paths:
                    file_hash = self._hash_file(filepath)
                    if file_hash:
                        hash_map[file_hash].append(filepath)

            duplicates = {
                h: paths for h, paths in hash_map.items() if len(paths) > 1
            }
            total_duplicates = sum(len(p) - 1 for p in duplicates.values())
            duplicate_groups = []

            for h, paths in duplicates.items():
                duplicate_groups.append({
                    "hash": h[:12] + "...",
                    "count": len(paths),

                    # ONLY filename, NOT full path
                    "sample_files": [os.path.basename(p) for p in paths[:3]],

                     # KEEP full paths internally (needed for actions)
                    "keep": paths[0],
                    "remove": paths[1:3],  # HARD LIMIT → max 2 paths
                    "remove_count": len(paths) - 1 
                })

            return ToolResult(
                success=True,
                data={
                    "duplicates": duplicate_groups,
                    "total_files_scanned": total,
                    "total_duplicate_files": total_duplicates,
                    "total_duplicate_groups": len(duplicate_groups),
                },
                message=f"Scanned {total} files. Found {total_duplicates} duplicates."
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Unexpected error: {str(e)}")