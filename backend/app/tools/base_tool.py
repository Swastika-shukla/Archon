from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolResult:
    """
    Standard output every tool must return.
    This way the Executor always knows what shape to expect back.
    """
    success: bool       # Did it work?
    data: Any = None    # The actual output
    message: str = ""   # Human readable summary
    error: str = None   # Error message if success=False


class BaseTool(ABC):
    """
    Every tool inherits from this.
    ABC = Abstract Base Class = Python forces child classes
    to implement all @abstractmethod methods.
    If a tool is missing run() for example, Python throws
    an error immediately — before you even run the app.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name. Used by SK and the registry."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Plain English. This gets sent to the LLM so it
        knows WHEN to use this tool. Write it clearly.
        """
        pass

    @property
    @abstractmethod
    def parameters(self) -> dict:
        """
        What inputs this tool needs.
        The Executor validates params against this before running.
        """
        pass

    @abstractmethod
    def run(self, params: dict, dry_run: bool = False) -> ToolResult:
        """
        The actual logic of the tool.
        dry_run=True means simulate only, no real file changes.
        """
        pass

    def validate_params(self, params: dict) -> tuple[bool, str]:
        """
        Called by Executor before run().
        Checks all required params are present.
        Returns (is_valid, error_message).
        """
        for param_name, config in self.parameters.items():
            if config.get("required", False) and param_name not in params:
                return False, f"Missing required parameter: '{param_name}'"
        return True, ""