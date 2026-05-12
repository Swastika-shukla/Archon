from dataclasses import dataclass, field
from typing import Any
from enum import Enum
import uuid
import json
import os
from datetime import datetime


class AgentStatus(Enum):
    PENDING = "pending"       # Session created, not started yet
    PLANNING = "planning"     # Planner is generating the task list
    RUNNING = "running"       # Orchestrator is executing steps
    COMPLETED = "completed"   # All steps finished successfully
    FAILED = "failed"         # Something went wrong
    DRY_RUN = "dry_run"       # Simulating only, no real file changes


@dataclass
class TaskStep:
    """Represents a single step in the agent's plan."""
    id: str                      # Unique ID for this step
    tool: str                    # Which tool to call e.g. detect_duplicates
    params: dict                 # Parameters to pass to the tool
    status: str = "pending"      # pending | running | done | failed
    result: Any = None           # Output from the tool after execution
    error: str = None            # Error message if step failed


@dataclass
class AgentState:
    """
    The single source of truth for one agent session.
    Every layer reads from and writes to this object.
    """
    # Core
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    goal: str = ""                            # Original user goal — never changes
    status: AgentStatus = AgentStatus.PENDING
    is_dry_run: bool = False                  # If True, no real file changes

    # Plan
    plan: list[TaskStep] = field(default_factory=list)         # Steps from Planner
    completed_steps: list[str] = field(default_factory=list)   # IDs of finished steps

    # Results
    results: dict[str, Any] = field(default_factory=dict)      # step_id → output
    observations: list[str] = field(default_factory=list)      # Summaries fed back to LLM

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def update_timestamp(self):
        """Call this whenever state changes."""
        self.updated_at = datetime.now().isoformat()

    def mark_step_done(self, step_id: str, result: Any):
        """Mark a step as completed and store its result."""
        for step in self.plan:
            if step.id == step_id:
                step.status = "done"
                step.result = result
                self.completed_steps.append(step_id)
                self.results[step_id] = result
                self.update_timestamp()
                break

    def mark_step_failed(self, step_id: str, error: str):
        """Mark a step as failed and store the error."""
        for step in self.plan:
            if step.id == step_id:
                step.status = "failed"
                step.error = error
                self.update_timestamp()
                break

    def add_observation(self, observation: str):
        """Add a human-readable summary — fed back into LLM context."""
        self.observations.append(observation)
        self.update_timestamp()

    def save(self, memory_dir: str = "memory"):
        """Save the full state to a local JSON file."""
        os.makedirs(memory_dir, exist_ok=True)
        path = os.path.join(memory_dir, f"{self.session_id}.json")
        with open(path, "w") as f:
            json.dump(self._to_dict(), f, indent=2)

    def _to_dict(self) -> dict:
        """Convert state to a JSON-serializable dictionary."""
        return {
            "session_id": self.session_id,
            "goal": self.goal,
            "status": self.status.value,
            "is_dry_run": self.is_dry_run,
            "plan": [
                {
                    "id": s.id,
                    "tool": s.tool,
                    "params": s.params,
                    "status": s.status,
                    "result": s.result,
                    "error": s.error,
                }
                for s in self.plan
            ],
            "completed_steps": self.completed_steps,
            "results": self.results,
            "observations": self.observations,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }   