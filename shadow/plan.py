"""Turn a recorded demonstration into a step plan with the planner model.

Usage: python -m shadow.plan runs/<id>
Writes runs/<id>/plan.json.
"""
import json
import sys
from pathlib import Path

from shadow import llm
from shadow.steps import ACTIONS, PlanError, validate_plan

# Keyframes cost prompt time on this machine, so only a few go to the model.
MAX_KEYFRAMES = 4

PLAN_SCHEMA = {
    "type": "object",
    "required": ["task", "steps"],
    "properties": {
        "task": {"type": "string"},
        "steps": {"type": "array", "items": {
            "type": "object",
            "required": ["intent", "action", "expected"],
            "properties": {
                "intent": {"type": "string"},
                "action": {"type": "string", "enum": list(ACTIONS)},
                "target": {"type": "object", "properties": {
                    "role": {"type": "string"}, "name": {"type": "string"}}},
                "value": {"type": "string"},
                "expected": {"type": "string"},
            },
        }},
    },
}

PROMPT = """You are Shadow. A person demonstrated a browser task once. Below is the event log
(one JSON object per line) and screenshots taken after some events.

Write a plan that repeats the task. Rules:
- Use only these actions: {actions}.
- Keep the role and name of each target exactly as in the event log.
- Drop events that do not change anything; merge duplicates.
- "intent" says what the step is for in plain words ("Pick the latest unpaid invoice"), not where to click.
- "expected" describes what the page should show right after the step, so someone can check it on a screenshot.
- "task" is one sentence describing the whole job.

Event log:
{events}
"""


def load_events(run_dir):
    with open(run_dir / "events.jsonl", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def pick_keyframes(events, run_dir):
    shots = [e["shot"] for e in events if e.get("shot")]
    if len(shots) > MAX_KEYFRAMES:
        stride = len(shots) / MAX_KEYFRAMES
        shots = [shots[int(i * stride)] for i in range(MAX_KEYFRAMES - 1)] + [shots[-1]]
    return [(run_dir / s).read_bytes() for s in shots]


def make_plan(run_dir, chat=llm.chat_json):
    events = load_events(run_dir)
    log = "\n".join(json.dumps({k: e.get(k) for k in ("type", "role", "name", "value", "url")}) for e in events)
    prompt = PROMPT.format(actions=", ".join(ACTIONS), events=log)
    plan = chat("planner", prompt, images_png=pick_keyframes(events, run_dir), schema=PLAN_SCHEMA)
    validate_plan(plan)
    with open(run_dir / "plan.json", "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)
    return plan


def main():
    run_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if run_dir is None or not (run_dir / "events.jsonl").is_file():
        print(f"No recording at {run_dir or '(no folder given)'}: expected events.jsonl inside it. "
              "Record one with: python -m shadow.record http://localhost:8000/demo_site/invoices.html")
        return 2
    try:
        llm.preflight(["planner"])
        plan = make_plan(run_dir)
    except (llm.LLMError, PlanError) as e:
        print(f"No plan: {e}")
        return 2
    for i, step in enumerate(plan["steps"], 1):
        print(f"{i}. [{step['action']}] {step['intent']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
