"""Run a plan step by step: act, check the screenshot, repair on failure.

Usage: python -m shadow.run runs/<id>/plan.json [--layout b] [--headless]
--layout <id> adds ?layout=<id> to every goto (b moves and renames the demo's export button).
Writes runs/<id>/exec/<exec_id>/run.json in the format of docs/interface.md.
"""
import argparse
import copy
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from shadow import llm
from shadow.compile import compile_plan
from shadow.steps import ACTIONS, PlanError, locate, validate_plan, validate_step

STEP_TIMEOUT_MS = 3000
MAX_REPAIRS_PER_STEP = 2
# Only used for the viewer's highlight box, so it must not slow a run down.
BBOX_TIMEOUT_MS = 500
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

TEXT_CHECK_PROMPT = """You check one step of a browser automation.
Step intent: {intent}
Expected state after the step: {expected}
Current page accessibility tree (role "name", with text and values):
{tree}
Does the page show the expected state? Reply with JSON: {{"ok": true/false, "reason": "..."}}"""

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


# Checker calls run with thinking off: on gemma4:e4b (CPU) it halved check time (46.8 s -> 24.1 s mean)
# with 6/6 correct verdicts either way. Repairs keep thinking on; they are rarer and harder.
def model_check(page, step):
    """Screenshot check: used for the final step and right after a repair, where a person would look."""
    reply = llm.chat_json("checker", CHECK_PROMPT.format(intent=step["intent"], expected=step["expected"]),
                          images_png=[page.screenshot()], schema=CHECK_SCHEMA, think=False)
    return bool(reply.get("ok")), str(reply.get("reason", ""))


def model_text_check(page, step):
    """Text-only check against the accessibility tree: cheaper, used for routine steps."""
    tree = page.locator("body").aria_snapshot()[:MAX_SNAPSHOT_CHARS]
    reply = llm.chat_json("checker", TEXT_CHECK_PROMPT.format(intent=step["intent"], expected=step["expected"], tree=tree),
                          schema=CHECK_SCHEMA, think=False)
    return bool(reply.get("ok")), str(reply.get("reason", ""))


def model_repair(page, step, problem):
    snapshot = page.locator("body").aria_snapshot()[:MAX_SNAPSHOT_CHARS]
    reply = llm.chat_json("planner", REPAIR_PROMPT.format(
        step=json.dumps(step), problem=problem, snapshot=snapshot, actions=", ".join(ACTIONS)),
        schema=REPAIR_SCHEMA)
    return reply.get("step"), str(reply.get("explanation", ""))


def seconds_since(t0):
    return round(time.perf_counter() - t0, 3)


def take_screenshot(page):
    try:
        return page.screenshot()
    except PlaywrightError:
        return None


def target_box(page, target):
    """Where the target sits in the viewport screenshot, in CSS pixels; None if it can't be found quickly."""
    try:
        box = locate(page, target).bounding_box(timeout=BBOX_TIMEOUT_MS)
    except PlaywrightError:
        return None
    return {k: round(v, 1) for k, v in box.items()} if box else None


def summarize(steps_log):
    ran = [s for s in steps_log if s["status"] != "not_run"]
    repairs_attempted = repairs_succeeded = 0
    for s in steps_log:
        for this, after in zip(s["attempts"], s["attempts"][1:] + [None]):
            if this["repair"] is None:
                continue
            repairs_attempted += 1
            if after and after["action_ok"] and after["check"] and after["check"]["ok"]:
                repairs_succeeded += 1
    return {
        "steps_total": len(steps_log),
        "steps_passed": sum(s["status"] in ("passed", "repaired") for s in steps_log),
        "repairs_attempted": repairs_attempted,
        "repairs_succeeded": repairs_succeeded,
        "time_per_step_s": round(sum(s["time_s"] for s in ran) / len(ran), 3) if ran else 0,
    }


def run_plan(page, plan, check=model_check, repair=model_repair, log=print, shots_dir=None, run_info=None,
             visual_check=None, step_timeout_ms=STEP_TIMEOUT_MS):
    """Run every step and build the run log described in docs/interface.md.

    Returns {"ok", "plan", "repairs", "failed_step", "log"}; the input plan is not modified.
    shots_dir: where to save per-attempt screenshots (None = don't save).
    run_info: top-level run.json fields the caller knows (recording_id, exec_id, layout, models).
    visual_check: if given, used instead of check for the final step and for attempts after a repair.
    step_timeout_ms: how long an action waits for its element; tests lower it so fake repairs start sooner.
    """
    plan = copy.deepcopy(validate_plan(plan))
    started_at = datetime.now().astimezone().isoformat(timespec="seconds")
    run_t0 = time.perf_counter()
    repairs = []
    failed_step = None
    steps_log = [{"index": i + 1, "status": "not_run", "planned": copy.deepcopy(s), "time_s": 0, "attempts": []}
                 for i, s in enumerate(plan["steps"])]
    page.set_default_timeout(step_timeout_ms)
    last = len(plan["steps"]) - 1

    for i, step in enumerate(plan["steps"]):
        entry = steps_log[i]
        step_t0 = time.perf_counter()
        repaired = False
        while True:
            n = len(entry["attempts"]) + 1
            log(f"[{i + 1}/{len(plan['steps'])}] {step['intent']}" + (f" (attempt {n})" if n > 1 else ""))
            attempt = {"attempt": n, "step": copy.deepcopy(step), "action_ok": False, "error": None, "check": None,
                       "screenshot": None, "bbox": None, "action_s": 0, "check_s": 0, "repair": None}
            entry["attempts"].append(attempt)

            t0 = time.perf_counter()
            try:
                do_step(page, step)
                attempt["action_ok"] = True
            except PlaywrightError as e:
                attempt["error"] = str(e).splitlines()[0]
            attempt["action_s"] = seconds_since(t0)

            png = take_screenshot(page)
            if png and shots_dir:
                name = f"{i + 1:03d}-{n}.png"
                (Path(shots_dir) / name).write_bytes(png)
                attempt["screenshot"] = "shots/" + name

            if attempt["action_ok"] and "target" in step:
                attempt["bbox"] = target_box(page, step["target"])

            if attempt["action_ok"]:
                use_visual = visual_check is not None and (i == last or repaired)
                t0 = time.perf_counter()
                ok, reason = (visual_check if use_visual else check)(page, step)
                attempt["check_s"] = seconds_since(t0)
                attempt["check"] = {"ok": bool(ok), "reason": reason, "used": "visual_check" if use_visual else "check"}
                problem = None if ok else f"Action ran but the check failed: {reason}"
            else:
                problem = "Action failed: " + attempt["error"]

            if problem is None:
                log("    ok")
                entry["status"] = "repaired" if repaired else "passed"
                break
            log(f"    {problem}")
            if n > MAX_REPAIRS_PER_STEP:
                log("    giving up on this step")
                entry["status"] = "failed"
                break

            t0 = time.perf_counter()
            new_step, explanation = repair(page, step, problem)
            attempt["repair"] = {"explanation": explanation, "new_step": new_step, "accepted": True, "repair_s": 0}
            try:
                validate_step(new_step, i)
            except PlanError as e:
                attempt["repair"]["accepted"] = False
                log(f"    repair rejected: {e}")
            attempt["repair"]["repair_s"] = seconds_since(t0)
            if attempt["repair"]["accepted"]:
                log(f"    repair: {explanation}")
                repairs.append({"step": i + 1, "before": step, "after": new_step, "explanation": explanation})
                step = plan["steps"][i] = new_step
                repaired = True

        entry["time_s"] = seconds_since(step_t0)
        if entry["status"] == "failed":
            failed_step = i + 1
            break

    info = {"recording_id": None, "exec_id": None, "layout": None, "models": {"planner": None, "checker": None}}
    info.update(run_info or {})
    run_log = {"schema_version": 1, **info, "task": plan.get("task"), "started_at": started_at,
               "duration_s": seconds_since(run_t0), "ok": failed_step is None, "failed_step": failed_step,
               "steps": steps_log, "summary": summarize(steps_log)}
    return {"ok": failed_step is None, "plan": plan, "repairs": repairs, "failed_step": failed_step, "log": run_log}


def save_run(exec_dir, result):
    """Write run.json, automation.py and (if anything was repaired) plan.repaired.json."""
    exec_dir = Path(exec_dir)
    exec_dir.mkdir(parents=True, exist_ok=True)
    (exec_dir / "run.json").write_text(json.dumps(result["log"], indent=2), encoding="utf-8")
    (exec_dir / "automation.py").write_text(compile_plan(result["plan"]), encoding="utf-8")
    if result["repairs"]:
        (exec_dir / "plan.repaired.json").write_text(json.dumps(result["plan"], indent=2), encoding="utf-8")


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


def layout_id(text):
    if not re.fullmatch(r"[a-z0-9-]{1,20}", text):
        raise argparse.ArgumentTypeError("layout ids are 1-20 lowercase letters, digits or dashes")
    return text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("--layout", type=layout_id, default=None)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    if args.layout:
        plan = with_layout(plan, args.layout)
    try:
        llm.preflight(["planner", "checker"])
    except llm.LLMError as e:
        print(f"Not ready: {e}")
        return 2

    rec_dir = args.plan.parent
    exec_id = time.strftime("%Y-%m-%d_%H%M%S")
    exec_dir = rec_dir / "exec" / exec_id
    (exec_dir / "shots").mkdir(parents=True)
    run_info = {
        "recording_id": rec_dir.name if (rec_dir / "events.jsonl").exists() else None,
        "exec_id": exec_id,
        "layout": args.layout,
        "models": {role: os.environ.get(env) for role, env in llm.ROLE_ENV.items()},
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        # Scale 1 keeps screenshot pixels equal to CSS pixels, which the viewer's bbox overlay relies on.
        page = browser.new_page(device_scale_factor=1)
        try:
            result = run_plan(page, plan, check=model_text_check, visual_check=model_check,
                              shots_dir=exec_dir / "shots", run_info=run_info)
        except llm.LLMError as e:
            # Ollama stopped or a reply was unusable mid-run; there is no complete run log to save.
            print(f"Stopped: {e}")
            return 2
        finally:
            browser.close()

    save_run(exec_dir, result)
    s = result["log"]["summary"]
    print(f"{s['steps_passed']}/{s['steps_total']} steps, {s['repairs_succeeded']}/{s['repairs_attempted']} repairs, "
          f"{s['time_per_step_s']} s per step. Run log: {exec_dir / 'run.json'}")
    print("DONE" if result["ok"] else f"FAILED at step {result['failed_step']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
