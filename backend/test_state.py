from app.agent.orchestrator import run_agent
from datetime import datetime

def divider(char="─", w=52): print(char * w)

goal = "Clean C:/Users/HP/Downloads — find duplicates then categorize files. No subfolders."

divider("═")
print("  ARCHON  ·  AI File Management Agent")
divider("═")
print(f"  Goal    : {goal[:48]}...")
print(f"  Mode    : DRY RUN (no real changes)")
print(f"  Started : {datetime.now().strftime('%H:%M:%S')}")
divider()

state = run_agent(goal=goal, dry_run=True)

divider()
print(f"  Status  : ✅ COMPLETED" if "COMPLETED" in str(state.status) else "  Status  : ❌ FAILED")
print(f"  Steps   : {len(state.plan)}")
divider()
print("  EXECUTION SUMMARY")
divider()
for i, obs in enumerate(state.observations, 1):
    clean = obs.replace("[DRY RUN] ", "").replace("detect_duplicates: ", "").replace("categorize_files: ", "")
    print(f"  {i}. {clean}")
divider("═")