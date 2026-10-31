"""Run a plan step by step: act, check the screenshot, repair on failure.

Usage: python -m shadow.run runs/<id>/plan.json [--layout b] [--headless]
--layout b opens the demo page with its export button moved and renamed.
"""
import argparse
import copy
import json
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from shadow import llm
from shadow.compile import compile_plan
from shadow.steps import ACTIONS, PlanError, locate, validate_plan, validate_step

STEP_TIMEOUT_MS = 3000
MAX_REPAIRS_PER_STEP = 2
# The accessibility snapshot is the repairer's map of the page; capped to keep prompts fast.
MAX_SNAPSHOT_CHARS = 6000

CHECK_SCHEMA = {"type": "object", "required": ["ok", "reason"],
                "properties": {"ok": {"type": "boolean"}, "reason": {"type": "string"}}}
REPAIR_SCHEMA = {"type": "object", "required": ["explanation", "step"], "properties": {
    "explanation": {"type": "string"},
    "step": {"type": "object", "required": ["intent", "action", "expected"], "properties": {
        "intent": {"type": "string"},
        "action": {"type": "string", "enum": list(ACTIONS)},
        "target": {"type": "object", "properties": {"role": {"type": "string"}, "name": {"type": "string"}}},
        "value": {"type": "string"},
        "expected": {"type": "string"},
    }},
}}

CHECK_PROMPT = """You check one step of a browser automation.
Step intent: {intent}
Expected state after the step: {expected}
Look at the screenshot. Does the page show the expected state? Reply with JSON: {{"ok": true/false, "reason": "..."}}"""

REPAIR_PROMPT = """You repair one step of a browser automation. The page may have changed since it was recorded.
Failed step (JSON): {step}
What went wrong: {problem}

Current page accessibility tree (role "name"):
{snapshot}

Return the same step with a corrected target that achieves the same intent on the current page.
Keep the action and intent unless they are the problem. Allowed actions: {actions}.
Reply with JSON: {{"explanation": "one sentence on what changed", "step": {{...}}}}"""


def do_step(page, step):
    action = step["action"]
    if action == "goto":
        page.goto(step["value"])
        return
    loc = locate(page, step["target"])
    if action == "click" and step["target"]["role"] in ("checkbox", "radio"):
        # check() is idempotent, so retrying after a repair cannot untick the box.
        loc.check()
    elif action == "click":
        loc.click()
    elif action == "fill":
        loc.fill(step["value"])
    elif action == "select":
        loc.select_option(label=step["value"])
    else:
        loc.press(step["value"])


def model_check(page, step):
    reply = llm.chat_json("checker", CHECK_PROMPT.format(intent=step["intent"], expected=step["expected"]),
                          images_png=[page.screenshot()], schema=CHECK_SCHEMA)
    return bool(reply.get("ok")), str(reply.get("reason", ""))


def model_repair(page, step, problem):
    snapshot = page.locator("body").aria_snapshot()[:MAX_SNAPSHOT_CHARS]
    reply = llm.chat_json("planner", REPAIR_PROMPT.format(
        step=json.dumps(step), problem=problem, snapshot=snapshot, actions=", ".join(ACTIONS)),
        schema=REPAIR_SCHEMA)
    return reply.get("step"), str(reply.get("explanation", ""))


def run_plan(page, plan, check=model_check, repair=model_repair, log=print):
    """Returns {"ok", "plan", "repairs", "failed_step"}; the input plan is not modified."""
    plan = copy.deepcopy(validate_plan(plan))
    repairs = []
    page.set_default_timeout(STEP_TIMEOUT_MS)
    for i, step in enumerate(plan["steps"]):
        attempts = 0
        while True:
            log(f"[{i + 1}/{len(plan['steps'])}] {step['intent']}")
            try:
                do_step(page, step)
                ok, reason = check(page, step)
                problem = None if ok else f"Action ran but the check failed: {reason}"
            except PlaywrightError as e:
                problem = "Action failed: " + str(e).splitlines()[0]
            if problem is None:
                log("    ok")
                break
            log(f"    {problem}")
            if attempts >= MAX_REPAIRS_PER_STEP:
                log("    giving up on this step")
                return {"ok": False, "plan": plan, "repairs": repairs, "failed_step": i + 1}
            attempts += 1
            new_step, explanation = repair(page, step, problem)
            try:
                validate_step(new_step, i)
            except PlanError as e:
                log(f"    repair rejected: {e}")
                continue
            log(f"    repair: {explanation}")
            repairs.append({"step": i + 1, "before": step, "after": new_step, "explanation": explanation})
            step = plan["steps"][i] = new_step
    return {"ok": True, "plan": plan, "repairs": repairs, "failed_step": None}


def with_layout(plan, layout):
    """Point every goto at the given demo layout (adds or replaces ?layout=)."""
    plan = copy.deepcopy(plan)
    for step in plan["steps"]:
        if step["action"] == "goto":
            parts = urlparse(step["value"])
            query = dict(parse_qsl(parts.query))
            query["layout"] = layout
            step["value"] = urlunparse(parts._replace(query=urlencode(query)))
    return plan


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("--layout", choices=["a", "b"], default="a")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    plan = with_layout(json.loads(args.plan.read_text(encoding="utf-8")), args.layout)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        result = run_plan(browser.new_page(), plan)
        browser.close()

    if result["repairs"]:
        out = args.plan.with_name("plan.repaired.json")
        out.write_text(json.dumps(result["plan"], indent=2), encoding="utf-8")
        args.plan.with_name("automation.py").write_text(compile_plan(result["plan"]), encoding="utf-8")
        print(f"{len(result['repairs'])} repair(s). Patched plan saved to {out}")
    print("DONE" if result["ok"] else f"FAILED at step {result['failed_step']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
