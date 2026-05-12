import os

# These folders are NEVER allowed to be touched by Archon
# No matter what the user asks
BLOCKED_PATHS = [
    "C:/Windows",
    "C:/Program Files",
    "C:/Program Files (x86)",
    "C:/ProgramData",
    os.path.expanduser("~/.ssh"),
    os.path.expanduser("~/AppData/Roaming"),
    os.path.expanduser("~/AppData/Local/Microsoft"),
]


def is_path_safe(path: str) -> tuple[bool, str]:
    """
    Checks if a single path is safe to operate on.
    Normalizes the path first so C:/WINDOWS and C:/windows
    both get caught by the same rule.
    Returns (is_safe, reason_if_blocked)
    """
    if not path:
        return False, "No path provided."

    normalized = os.path.normpath(path).lower()

    for blocked in BLOCKED_PATHS:
        blocked_normalized = os.path.normpath(blocked).lower()
        if normalized.startswith(blocked_normalized):
            return False, f"Access denied: '{path}' is a protected system path."

    return True, ""


def extract_paths_from_params(params: dict) -> list[str]:
    """
    Pulls out all path-like values from a tool's params.
    We check every path, not just the first one.
    """
    path_keys = ["path", "source", "destination", "target", "folder", "files"]
    paths = []
    for key in path_keys:
        value = params.get(key)
        if isinstance(value, str):
            paths.append(value)
        elif isinstance(value, list):
            # e.g. move_files passes a list of file paths
            paths.extend([v for v in value if isinstance(v, str)])
    return paths


def check_params_safety(params: dict) -> tuple[bool, str]:
    """
    Runs safety check on ALL paths found in params at once.
    Called by Executor before every single tool run.
    Returns (is_safe, error_message)
    """
    paths = extract_paths_from_params(params)

    if not paths:
        return True, ""

    for path in paths:
        is_safe, reason = is_path_safe(path)
        if not is_safe:
            return False, reason

    return True, ""