import os
import importlib
import inspect
import logging
from app.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
print("🔥 TOOL DISCOVERY STARTED")

TOOL_REGISTRY: dict = {}


def _discover_tools():
    """
    Scans app/tools/ directory, imports every module,
    finds all BaseTool subclasses, and registers them.
    Runs once at startup automatically.
    """
    tools_dir = os.path.dirname(__file__)

    for filename in os.listdir(tools_dir):
        # Skip non-python files and unwanted files
        if not filename.endswith(".py"):
            continue
        if filename.startswith("__"):
            continue
        if filename == "base_tool.py":
            continue

        module_name = f"app.tools.{filename[:-3]}"  # remove .py

        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            logger.warning(f"Could not import '{module_name}': {e}")
            continue

        # Inspect classes inside module
        for _, obj in inspect.getmembers(module, inspect.isclass):

            # ✅ Only pick classes defined in THIS module (very important fix)
            if obj.__module__ != module.__name__:
                continue

            # ✅ Must inherit from BaseTool (but not BaseTool itself)
            if not issubclass(obj, BaseTool) or obj is BaseTool:
                continue

            try:
                instance = obj()
                tool_name = instance.name

                # Prevent duplicate tool names
                if tool_name in TOOL_REGISTRY:
                    logger.warning(
                        f"Duplicate tool name '{tool_name}' in '{module_name}' — skipping."
                    )
                    continue

                TOOL_REGISTRY[tool_name] = instance
                print(f"Registered tool: '{tool_name}' from '{module_name}'")

            except Exception as e:
                logger.warning(f"Could not instantiate tool in '{module_name}': {e}")


# ✅ Run auto-discovery when package is imported
_discover_tools()


def get_tool(name: str):
    """
    Returns a tool instance by name.
    Returns None if not found.
    """
    return TOOL_REGISTRY.get(name)


def list_tools() -> list[dict]:
    """
    Returns all registered tools with name, description, parameters.
    This is used in:
    - Planner prompt
    - Orchestrator system prompt
    """
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }
        for tool in TOOL_REGISTRY.values()
    ]