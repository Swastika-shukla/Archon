import os
import json
import re
import logging
import asyncio

from app.agent.kernel import get_kernel
from app.agent.state import AgentState, AgentStatus, TaskStep
from app.core.executor import Executor
from app.tools import list_tools
from app.utils.truncation import truncate_string

from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
from semantic_kernel.connectors.ai.prompt_execution_settings import PromptExecutionSettings

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MAX_ITERATIONS = 6


async def _stream(websocket, event_type: str, step: int, data: dict):
    if websocket is None:
        return
    try:
        await websocket.send_json({"type": event_type, "step": step, "data": data})
    except Exception:
        pass


def get_user_folders():
    home = os.path.expanduser("~")

    def get_windows_folder(folder_id):
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
            )
            path, _ = winreg.QueryValueEx(key, folder_id)
            return path.replace("\\", "/")
        except Exception:
            return None

    downloads = get_windows_folder("{374DE290-123F-4565-9164-39C4925E467B}") or os.path.join(home, "Downloads").replace("\\", "/")
    documents = get_windows_folder("Personal") or os.path.join(home, "Documents").replace("\\", "/")
    desktop = get_windows_folder("Desktop") or os.path.join(home, "Desktop").replace("\\", "/")

    return home, downloads, documents, desktop


def build_system_prompt() -> str:
    tools = list_tools()
    tools_description = json.dumps(tools, indent=2)
    home, downloads, documents, desktop = get_user_folders()

    return f"""You are Archon, an AI agent that helps users manage files on Windows.

Known folder paths:
- Home: {home}
- Downloads: {downloads}
- Documents: {documents}
- Desktop: {desktop}

Available tools:
{tools_description}

RESPONSE FORMAT:
Always respond with ONLY a valid JSON object - no markdown, no explanation.

To call a tool:
{{
  "action": "tool_name",
  "params": {{"param1": "value1"}},
  "reasoning": "brief explanation"
}}

When done:
{{
  "action": "finish",
  "params": {{}},
  "reasoning": "what was done"
}}

When you need a folder path or session ID from the user:
{{
  "action": "ask_user",
  "params": {{"question": "your question"}},
  "reasoning": "what you need"
}}

RULES:
- Never operate on system paths: C:/Windows, C:/Program Files, C:/ProgramData
- Never permanently delete files - safe_delete moves to recycle bin only
- Never invent file data - always run a tool first
- Never use recursive: true unless user asks for subfolders
- If a folder path is given in the goal, use it directly
- If no folder is given and cannot be inferred, use ask_user
- Accept any valid path the user provides
- Only call tools relevant to what the user asked - nothing extra
- After each tool result, decide next step based on the goal and what was returned
- If the user sends a greeting or casual message with no file task, call ask_user to ask what they need help with
"""


def parse_llm_response(response_text: str) -> dict | None:
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                return None
    return None


def build_observation(tool_name: str, data: dict, message: str, step: int) -> str:
    if not data:
        return truncate_string(f"Step {step}: {tool_name} completed. {message}", 250)

    if tool_name == "list_files":
        total = data.get("total_files", 0)
        path = data.get("path", "")
        sample = data.get("sample_files", [])
        if total == 0:
            return f"Step {step}: folder '{os.path.basename(path)}' is empty."
        return truncate_string(
            f"Step {step}: found {total} files in '{os.path.basename(path)}'. Sample: {', '.join(sample[:5])}.",
            300
        )

    elif tool_name == "find_file_by_name":
        found = data.get("found", False)
        matches = data.get("matches", [])
        total = data.get("total_found", 0)
        if found:
            return truncate_string(
                f"Step {step}: found {total} match(es). Paths: {', '.join(matches[:3])}.",
                350
            )
        return f"Step {step}: no files matched the search."

    elif tool_name == "detect_duplicates":
        total = data.get("total_files_scanned", 0)
        dupes = data.get("total_duplicate_files", 0)
        groups = data.get("total_duplicate_groups", 0)
        duplicate_list = data.get("duplicates", [])

        if dupes == 0:
            return f"Step {step}: scanned {total} files. No duplicates found."

        files_to_remove = []
        for group in duplicate_list:
            files_to_remove.extend(group.get("remove", []))
        sample = [os.path.basename(p) for p in files_to_remove[:5]]

        return truncate_string(
            f"Step {step}: scanned {total} files. Found {dupes} duplicates in {groups} groups. "
            f"Sample: {', '.join(sample)}. Full paths available in duplicates data.",
            400
        )

    elif tool_name == "categorize_files":
        total = data.get("total_files", 0)
        categories = data.get("categorized", {})
        if not categories:
            return f"Step {step}: no files found to categorize."
        breakdown = [f"{cat}({len(files)})" for cat, files in categories.items()]
        lines = [f"Step {step}: categorized {total} files. {', '.join(breakdown)}."]
        for cat, files in categories.items():
            paths = [f["full_path"] for f in files[:3] if "full_path" in f]
            if paths:
                lines.append(f"{cat}: {', '.join(paths)}")
        return truncate_string("\n".join(lines), 900)

    elif tool_name == "move_files":
        moved = data.get("total_moved", 0)
        skipped = data.get("total_skipped", 0)
        return f"Step {step}: moved {moved} files. Skipped {skipped}."

    elif tool_name == "safe_delete":
        deleted = data.get("total_deleted", 0)
        skipped = data.get("total_skipped", 0)
        return f"Step {step}: moved {deleted} files to recycle bin. Skipped {skipped}."

    elif tool_name == "undo_session":
        undone = data.get("undone", 0)
        skipped = data.get("skipped", 0)
        files = data.get("files", [])
        return truncate_string(
            f"Step {step}: restored {undone} files. Skipped {skipped}. Files: {', '.join(files[:3])}.",
            250
        )

    return truncate_string(f"Step {step}: {tool_name} completed. {message}", 250)


def build_summary(tool_name: str, data: dict, message: str, step: int) -> str:
    if not data:
        return message

    if tool_name == "list_files":
        return ""

    elif tool_name == "find_file_by_name":
        found = data.get("found", False)
        matches = data.get("matches", [])
        total = data.get("total_found", 0)
        if found:
            names = [os.path.basename(p) for p in matches[:3]]
            return f"Found {total} matching file(s): {', '.join(names)}."
        return "No matching files found."

    elif tool_name == "detect_duplicates":
        total = data.get("total_files_scanned", 0)
        dupes = data.get("total_duplicate_files", 0)
        groups = data.get("total_duplicate_groups", 0)
        if dupes == 0:
            return f"Scanned {total} files. No duplicates found."
        return f"Scanned {total} files. Found {dupes} duplicates in {groups} groups."

    elif tool_name == "categorize_files":
        total = data.get("total_files", 0)
        categories = data.get("categorized", {})
        breakdown = [f"{cat}: {len(files)}" for cat, files in categories.items()]
        return f"Categorized {total} files - {' · '.join(breakdown[:4])}."

    elif tool_name == "move_files":
        moved = data.get("total_moved", 0)
        skipped = data.get("total_skipped", 0)
        if moved == 0:
            return f"No files moved. {skipped} skipped."
        return f"Moved {moved} file(s). {skipped} skipped."

    elif tool_name == "safe_delete":
        deleted = data.get("total_deleted", 0)
        skipped = data.get("total_skipped", 0)
        prefix = "Simulated: " if "[DRY RUN]" in message else ""
        return f"{prefix}Moved {deleted} file(s) to recycle bin. {skipped} skipped."

    elif tool_name == "undo_session":
        undone = data.get("undone", 0)
        skipped = data.get("skipped", 0)
        files = data.get("files", [])
        return f"Restored {undone} file(s). Skipped {skipped}. Files: {', '.join(files[:3]) if files else 'none'}."

    if tool_name == "ask_user":
        return ""

    return message


class Orchestrator:

    def __init__(self):
        self.kernel = get_kernel()
        self.executor = Executor()

    def _get_chat_service(self):
        return self.kernel.get_service(type=OpenAIChatCompletion)

    async def run(self, state: AgentState, websocket=None) -> AgentState:
        print(f"  Goal: {state.goal}")
        state.status = AgentStatus.RUNNING

        await _stream(websocket, "start", 0, {
            "goal": state.goal,
            "dry_run": state.is_dry_run
        })

        chat_history = ChatHistory()
        chat_history.add_system_message(build_system_prompt())

        paths_found = re.findall(r"[A-Za-z]:[/\\][^\s,]+", state.goal)
        path_hint = ""
        if paths_found:
            normalized = [p.replace("\\", "/") for p in paths_found]
            path_hint = f"\nPaths in goal: {json.dumps(normalized)} - use these exactly."

        chat_history.add_user_message(
            f"Goal: {state.goal}\n"
            f"Mode: {'DRY RUN - simulate only' if state.is_dry_run else 'LIVE - real changes allowed'}"
            f"{path_hint}"
        )

        chat_service = self._get_chat_service()
        settings = PromptExecutionSettings(temperature=0.1, max_tokens=400)

        step_counter = 0

        while step_counter < MAX_ITERATIONS:
            step_counter += 1
            print(f"  Iteration {step_counter}/{MAX_ITERATIONS}")

            await _stream(websocket, "iteration", step_counter, {
                "iteration": step_counter,
                "max": MAX_ITERATIONS
            })

            try:
                response = await chat_service.get_chat_message_content(
                    chat_history=chat_history,
                    settings=settings,
                    kernel=self.kernel,
                )

                response_text = str(response)
                parsed = parse_llm_response(response_text)

                if not parsed:
                    logger.warning("Invalid JSON from LLM. Retrying...")
                    chat_history.add_user_message("Respond with ONLY a valid JSON object.")
                    continue

                action = parsed.get("action")
                params = parsed.get("params", {})
                reasoning = parsed.get("reasoning", "")

                print(f"  Action: {action} - {reasoning}")

                await _stream(websocket, "thought", step_counter, {
                    "action": action,
                    "reasoning": reasoning
                })

                # ── ask_user ──────────────────────────────────────────
                if action == "ask_user":
                    question = params.get("question", "Could you provide more details?")
                    state.add_observation(f"Asked: {question}")

                    await _stream(websocket, "ask_user", step_counter, {
                        "question": question
                    })

                    if websocket is not None:
                        try:
                            raw = await asyncio.wait_for(
                                websocket.receive_text(), timeout=300
                            )
                            user_data = json.loads(raw)
                            user_answer = (
                                user_data.get("answer")
                                or user_data.get("goal")
                                or raw.strip()
                            )

                            if user_answer:
                                # Extract any path from answer
                                extracted = re.findall(r"[A-Za-z]:[/\\][^\s,]+", user_answer)
                                normalized = [p.replace("\\", "/") for p in extracted]
                                path_note = ""
                                if normalized:
                                    path_note = f"\nPath from user: {normalized[0]} - use this exactly as the path parameter."

                                chat_history.add_assistant_message(response_text)
                                chat_history.add_user_message(
                                    f"User answered: '{user_answer}'"
                                    f"{path_note}\n"
                                    f"Original goal: {state.goal}\n"
                                    f"Now proceed. Use the path above directly."
                                )
                                state.add_observation(f"User answered: {user_answer}")
                                continue

                        except asyncio.TimeoutError:
                            state.add_observation("Timed out waiting for user.")
                        except Exception as ex:
                            state.add_observation(f"Error: {str(ex)}")

                    state.status = AgentStatus.COMPLETED
                    state.save()
                    await _stream(websocket, "complete", step_counter, {
                        "session_id": state.session_id,
                        "status": state.status.value,
                        "observations": state.observations,
                        "steps_run": step_counter
                    })
                    break

                # ── finish ────────────────────────────────────────────
                if action == "finish":
                    state.status = AgentStatus.COMPLETED
                    state.add_observation(f"Completed: {reasoning}")
                    state.save()
                    await _stream(websocket, "complete", step_counter, {
                        "session_id": state.session_id,
                        "status": state.status.value,
                        "observations": state.observations,
                        "steps_run": step_counter
                    })
                    break

                # ── tool execution ────────────────────────────────────
                step_id = f"step_{step_counter}"
                task_step = TaskStep(id=step_id, tool=action, params=params)
                state.plan.append(task_step)

                await _stream(websocket, "action", step_counter, {
                    "tool": action,
                    "params": params
                })

                result = self.executor.run_step(task_step, state)

                if result.success:
                    observation = build_observation(action, result.data, result.message, step_counter)
                    await _stream(websocket, "tool_result", step_counter, {
                        "tool": action,
                        "success": True,
                        "message": result.message
                    })
                    summary_text = build_summary(action, result.data, result.message, step_counter)
                    if summary_text:
                        await _stream(websocket, "summary", step_counter, {
                            "text": summary_text
                        })
                else:
                    observation = (
                        f"Step {step_counter}: {action} failed. "
                        f"Error: {result.error}. Try a different approach."
                    )
                    await _stream(websocket, "tool_result", step_counter, {
                        "tool": action,
                        "success": False,
                        "error": result.error
                    })
                    await _stream(websocket, "summary", step_counter, {
                        "text": f"⚠️ {action} failed. {result.error}"
                    })

                print(f"  {observation}")
                await _stream(websocket, "observation", step_counter, {
                    "text": observation
                })

                chat_history.add_assistant_message(response_text)
                chat_history.add_user_message(
                    f"Observation: {observation}\nWhat is the next action?"
                )

            except Exception as e:
                logger.error(f"Loop error: {str(e)}")
                state.status = AgentStatus.FAILED
                state.save()
                await _stream(websocket, "error", step_counter, {"message": str(e)})
                raise

        if step_counter >= MAX_ITERATIONS and state.status == AgentStatus.RUNNING:
            logger.warning("Max iterations reached.")
            state.status = AgentStatus.COMPLETED
            await _stream(websocket, "complete", step_counter, {
                "session_id": state.session_id,
                "status": state.status.value,
                "observations": state.observations,
                "steps_run": step_counter
            })

        state.save()
        print("  Agent finished.")
        return state


def run_agent(goal: str, dry_run: bool = True) -> AgentState:
    state = AgentState(goal=goal, is_dry_run=dry_run)
    orchestrator = Orchestrator()
    return asyncio.run(orchestrator.run(state))