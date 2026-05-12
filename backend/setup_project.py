import os

folders = [
    "app/agent",
    "app/tools",
    "app/core",
    "app/api",
    "memory",
]

files = [
    "app/__init__.py",
    "app/agent/__init__.py",
    "app/agent/state.py",
    "app/agent/planner.py",
    "app/agent/orchestrator.py",
    "app/agent/controller.py",
    "app/tools/__init__.py",
    "app/tools/base_tool.py",
    "app/tools/detect_duplicates.py",
    "app/tools/move_files.py",
    "app/tools/categorize_files.py",
    "app/tools/safe_delete.py",
    "app/core/__init__.py",
    "app/core/executor.py",
    "app/core/safety.py",
    "app/api/__init__.py",
    "app/api/routes.py",
    "main.py",
    ".env",
    "requirements.txt",
    ".gitignore",
]

gitignore_content = """venv/
.env
__pycache__/
*.pyc
memory/
"""

print("Creating Archon project structure...")

for folder in folders:  
    os.makedirs(folder, exist_ok=True)
    print(f"  Created folder: {folder}")

for file in files:
    if not os.path.exists(file):
        with open(file, "w") as f:
            if file == ".gitignore":
                f.write(gitignore_content)
        print(f"  Created file: {file}")

print("\n✅ Archon project structure created successfully!")