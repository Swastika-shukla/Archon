import json
import logging
import asyncio
from app.agent.kernel import get_kernel
from app.tools import list_tools
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
from semantic_kernel.connectors.ai.prompt_execution_settings import PromptExecutionSettings

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def build_planner_prompt() -> str:
    tools = list_tools()
    tools_description = json.dumps(tools, indent=2)

    return f"""You are a planning assistant for an AI file management agent.

Your only job is to read a user goal and return a structured plan.

Available tools:
{tools_description}

RESPONSE FORMAT:
Return ONLY a valid JSON array. No markdown, no explanation, nothing else.

[
  {{
    "step": 1,
    "tool": "tool_name",
    "params": {{"param_key": "param_value"}},
    "reason": "why this step is needed"
  }}
]

RULES:
- Only use tools from the list above
- Use real Windows paths like C:/Users/HP/Downloads
- Order steps logically (scan before delete, categorize before move)
- Minimum steps needed to complete the goal
- Never include system paths like C:/Windows
- Return the JSON array only — no other text
"""


def parse_plan_response(response_text: str) -> list[dict] | None:
    text = response_text.strip()

    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
        return None
    except json.JSONDecodeError:
        start = text.find("[")
        end = text.rfind("]") + 1
        if start != -1 and end > start:
            try:
                parsed = json.loads(text[start:end])
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
        return None


class Planner:
    """
    Generates a structured execution plan from a natural language goal
    BEFORE the Orchestrator runs. Does NOT execute anything.
    """

    def __init__(self):
        self.kernel = get_kernel()
        self.chat_service = self.kernel.get_service(type=OpenAIChatCompletion)
        self.settings = PromptExecutionSettings(temperature=0.1, max_tokens=600)

    async def generate(self, goal: str) -> list[dict]:
        chat_history = ChatHistory()
        chat_history.add_system_message(build_planner_prompt())
        chat_history.add_user_message(f"Goal: {goal}")

        for attempt in range(1, 3):
            print(f"  ◆ Planner attempt {attempt} for: '{goal}'")

            response = await self.chat_service.get_chat_message_content(
                chat_history=chat_history,
                settings=self.settings,
                kernel=self.kernel,
            )

            response_text = str(response)
            plan = parse_plan_response(response_text)

            if plan is None:
                print(f"  ✗ Attempt {attempt}: Could not parse plan JSON. Retrying...")
                chat_history.add_assistant_message(response_text)
                chat_history.add_user_message(
                    "Your response was not valid JSON. Return ONLY a JSON array, nothing else."
                )
                continue

            print(f"  ✅ Plan generated: {len(plan)} steps.")
            return plan

        raise ValueError("Planner failed to generate a valid plan after 2 attempts.")

    def generate_sync(self, goal: str) -> list[dict]:
        """Synchronous wrapper — matches controller.run_sync() pattern."""
        return asyncio.run(self.generate(goal))
        
        