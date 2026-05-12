import os
from app.agent.state import AgentState, AgentStatus
from app.agent.orchestrator import Orchestrator
import asyncio

class AgentController:
    """
    Entry point for all agent runs.
    API calls this — never calls Orchestrator directly.
    """

    def __init__(self):
        self.orchestrator = Orchestrator()

    def validate_goal(self, goal: str) -> tuple[bool, str]:
        if not goal or not goal.strip():
            return False, "Please type something."
        if len(goal) > 500:
            return False, "Goal is too long. Keep it under 500 characters."
        return True, ""

    async def run(self, goal: str, dry_run: bool = True) -> AgentState:
        is_valid, error = self.validate_goal(goal)
        if not is_valid:
            state = AgentState(goal=goal)
            state.status = AgentStatus.FAILED
            state.add_observation(f"Validation failed: {error}")
            return state

        state = AgentState(goal=goal.strip(), is_dry_run=dry_run)
        return await self.orchestrator.run(state)

    def run_sync(self, goal: str, dry_run: bool = True) -> AgentState:
        """Synchronous wrapper for non-async contexts."""
        return asyncio.run(self.run(goal, dry_run))