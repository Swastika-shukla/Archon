import time
import logging
from app.core.safety import check_params_safety
from app.agent.state import AgentState, TaskStep
from app.tools import get_tool
from app.tools.base_tool import ToolResult

# Logger — prints timestamped messages to terminal during execution
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

MAX_RETRIES = 3    # How many times to retry a failed tool
RETRY_DELAY = 2    # Base seconds to wait between retries


class Executor:
    """
    The Executor is the ONLY part of Archon that directly calls tools.
    Everything goes through here — no exceptions.

    The flow for every single step:
    1. Find the tool in registry
    2. Validate params match tool's expected schema
    3. Safety check all file paths
    4. If dry_run → simulate, don't touch real files
    5. Execute tool with retry logic
    6. Update AgentState with result or error
    7. Save state to memory/
    """

    def run_step(self, step: TaskStep, state: AgentState) -> ToolResult:
        """
        Runs a single TaskStep safely.
        Called by the Orchestrator for each step in the agentic loop.
        """
        logger.info(f"Starting step '{step.id}' | Tool: '{step.tool}'")

        # ── Step 1: Find tool ─────────────────────────────────────────
        tool = get_tool(step.tool)
        if not tool:
            error = f"Tool '{step.tool}' not found in registry."
            logger.error(error)
            state.mark_step_failed(step.id, error)
            return ToolResult(success=False, error=error)

        # ── Step 2: Validate params ───────────────────────────────────
        is_valid, validation_error = tool.validate_params(step.params)
        if not is_valid:
            logger.error(f"Param validation failed: {validation_error}")
            state.mark_step_failed(step.id, validation_error)
            return ToolResult(success=False, error=validation_error)

        # ── Step 3: Safety check ──────────────────────────────────────
        is_safe, safety_error = check_params_safety(step.params)
        if not is_safe:
            logger.warning(f"Safety check BLOCKED step: {safety_error}")
            state.mark_step_failed(step.id, safety_error)
            return ToolResult(success=False, error=safety_error)

        # ── Step 4: Dry run ───────────────────────────────────────────
        # In dry run mode we call the tool but pass dry_run=True
        # Tools use this flag to simulate without touching real files
        if state.is_dry_run:
            logger.info(f"[DRY RUN] Simulating step '{step.id}'")
            result = tool.run(params=step.params, dry_run=True)
            state.mark_step_done(step.id, result.data)
            state.add_observation(f"[DRY RUN] {step.tool}: {result.message}")
            return result

        # ── Step 5: Execute with retries ──────────────────────────────
        # Exponential backoff: wait 2s, then 4s, then 6s between retries
        # This handles temporary failures like a locked file
        attempt = 0
        last_error = None

        while attempt < MAX_RETRIES:
            try:
                attempt += 1
                logger.info(f"Executing '{step.tool}' (attempt {attempt}/{MAX_RETRIES})")

                result = tool.run(params=step.params, dry_run=False)

                if result.success:
                    # ── Step 6: Update state on success ───────────────
                    state.mark_step_done(step.id, result.data)
                    state.add_observation(f"{step.tool}: {result.message}")
                    # ── Step 7: Save state to memory/ ─────────────────
                    state.save()
                    logger.info(f"Step '{step.id}' completed successfully.")
                    return result
                else:
                    last_error = result.error
                    logger.warning(f"Tool returned failure (attempt {attempt}): {last_error}")

            except Exception as e:
                last_error = str(e)
                logger.error(f"Exception on attempt {attempt}: {last_error}")

            # Wait before retrying — doubles each time
            if attempt < MAX_RETRIES:
                wait = RETRY_DELAY * attempt
                logger.info(f"Retrying in {wait}s...")
                time.sleep(wait)

        # ── All retries exhausted ─────────────────────────────────────
        final_error = f"Failed after {MAX_RETRIES} attempts. Last error: {last_error}"
        logger.error(final_error)
        state.mark_step_failed(step.id, final_error)
        state.save()
        return ToolResult(success=False, error=final_error)