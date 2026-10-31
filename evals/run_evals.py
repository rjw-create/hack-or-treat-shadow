"""Eval suite: every task x layout x run, one raw JSONL line each, plus a summary.

Usage (from the repo root):
  python -m evals.run_evals --mode fake             pipeline test, no model
  python -m evals.run_evals --mode gemma --runs 3   real Gemma 4 through Ollama (SHADOW_*_MODEL)

Fake mode is a pipeline test only: the checker always says ok and the repairer is an oracle that
already knows the answer. Its numbers say nothing about Gemma's ability.

Metrics come from the runner's run.json (run_plan() returns it as result["log"]); each raw line
embeds that whole run log so nothing is lost.
"""
import argparse
import copy
import functools
import http.server
import json
import statistics
import sys
import threading
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from shadow import llm
from shadow.run import model_check, model_repair, run_plan, with_layout

ROOT = Path(__file__).resolve().parent.parent
SUITE = ROOT / "evals" / "suite.json"
RESULTS = ROOT / "results"
END_STATE_TIMEOUT_MS = 3000
FAKE_NOTE = ("PIPELINE TEST, NOT A MODEL RESULT: the fake checker always says ok and the fake repairer "
             "knows the answer. These numbers say nothing about Gemma's ability.")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def start_server():
    handler = functools.partial(QuietHandler, directory=str(ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def point_at(plan, port):
    """Send every goto to the local eval server instead of the port written in the task file."""
    plan = copy.deepcopy(plan)
    for step in plan["steps"]:
        if step["action"] == "goto":
            parts = urlparse(step["value"])
            step["value"] = urlunparse(parts._replace(netloc=f"127.0.0.1:{port}"))
    return plan


def always_ok(page, step):
    return True, "fake check"


def oracle_repair(fixes):
    """Fake repairer with the answer key: fixes maps an old target name to step fields to override
    (null removes a field), so it can also change the action, e.g. a dropdown that became radios."""
    def repair(page, step, problem):
        fixed = copy.deepcopy(step)
        name = (step.get("target") or {}).get("name")
        if name not in fixes:
            return fixed, "Oracle has no fix for this step."
        for key, value in fixes[name].items():
            if value is None:
                fixed.pop(key, None)
            else:
                fixed[key] = copy.deepcopy(value)
        return fixed, f"Oracle: {name} is now {fixed['target']['name']}."
    return repair


def end_state_ok(page, done_when):
    """Ground truth read from the page itself, independent of the checker model."""
    try:
        text = page.get_by_role(done_when["role"]).first.text_content(timeout=END_STATE_TIMEOUT_MS)
    except PlaywrightError:
        return False
    return (text or "").strip() == done_when["text"]


def run_one(browser, plan, check, repair, done_when, run_info):
    """Run one plan in a fresh page; returns metrics plus the runner's full run.json as run_log."""
    page = browser.new_page()
    error = None
    try:
        result = run_plan(page, plan, check=check, repair=repair, log=lambda msg: None, run_info=run_info)
    except Exception as e:  # e.g. Ollama down or bad JSON: end this run, keep the suite going
        first_line = str(e).splitlines()[0] if str(e) else ""
        error = f"{type(e).__name__}: {first_line}"
        result = None
    end_ok = end_state_ok(page, done_when)
    page.close()

    if result is None:
        # run_plan raised before building its log, so there are no step-level numbers for this run.
        return {"ok": False, "end_state_ok": end_ok, "task_success": False, "failed_step": None, "error": error,
                "steps_total": len(plan["steps"]), "steps_run": 0, "steps_passed": 0, "attempts": 0,
                "attempts_per_step": [], "repairs_attempted": 0, "repairs_succeeded": 0, "duration_s": None,
                "step_times_s": [], "time_per_step_s": None, "run_log": None}

    run_log = result["log"]
    ran = [s for s in run_log["steps"] if s["status"] != "not_run"]
    summary = run_log["summary"]
    return {
        "ok": run_log["ok"],
        "end_state_ok": end_ok,
        "task_success": run_log["ok"] and end_ok,
        "failed_step": run_log["failed_step"],
        "error": error,
        "steps_total": summary["steps_total"],
        "steps_run": len(ran),
        "steps_passed": summary["steps_passed"],
        "attempts": sum(len(s["attempts"]) for s in ran),
        "attempts_per_step": [len(s["attempts"]) for s in ran],
        "repairs_attempted": summary["repairs_attempted"],
        "repairs_succeeded": summary["repairs_succeeded"],
        "duration_s": run_log["duration_s"],
        "step_times_s": [s["time_s"] for s in ran],
        "time_per_step_s": summary["time_per_step_s"],
        "run_log": run_log,
    }


def aggregate(records):
    attempted = sum(r["repairs_attempted"] for r in records)
    succeeded = sum(r["repairs_succeeded"] for r in records)
    step_times = [t for r in records for t in r["step_times_s"]]
    return {
        "runs": len(records),
        "task_success_rate": round(statistics.mean(r["task_success"] for r in records), 3),
        "runner_ok_rate": round(statistics.mean(r["ok"] for r in records), 3),
        "repairs_attempted": attempted,
        "repairs_succeeded": succeeded,
        "repair_success_rate": round(succeeded / attempted, 3) if attempted else None,
        "steps_per_task": round(statistics.mean(r["attempts"] for r in records), 2),
        "time_per_step_s": round(statistics.mean(step_times), 3) if step_times else None,
        "errors": sum(1 for r in records if r["error"]),
    }


def summarize(records):
    groups = {}
    for r in records:
        groups.setdefault((r["task"], r["layout"]), []).append(r)
    return {
        "overall": aggregate(records),
        "by_task_layout": [{"task": t, "layout": lay, **aggregate(rs)} for (t, lay), rs in sorted(groups.items())],
    }


def select(suite, tasks=None, layouts=None):
    """Keep only the named tasks and layouts (None keeps all); unknown names are an error, not a silent no-op."""
    known_tasks = {t["id"] for t in suite["tasks"]}
    known_layouts = {lay for t in suite["tasks"] for lay in t["layouts"]}
    unknown = sorted(set(tasks or ()) - known_tasks) + sorted(set(layouts or ()) - known_layouts)
    if unknown:
        raise ValueError(f"not in the suite: {', '.join(unknown)}")
    picked = []
    for task in suite["tasks"]:
        if tasks and task["id"] not in tasks:
            continue
        kept = [lay for lay in task["layouts"] if not layouts or lay in layouts]
        if kept:
            picked.append({**task, "layouts": kept})
    return {**suite, "tasks": picked}


def run_suite(mode, runs, out_dir, suite_path=SUITE, tasks=None, layouts=None):
    """Run the suite, or the chosen tasks/layouts of it; returns (records, summary, jsonl_path, summary_path)."""
    suite = select(json.loads(suite_path.read_text(encoding="utf-8")), tasks, layouts)
    if mode == "fake":
        models = {"planner": "fake", "checker": "fake"}
    else:
        models = {"planner": llm.model_for("planner"), "checker": llm.model_for("checker")}
    note = FAKE_NOTE if mode == "fake" else "Real model run through Ollama."

    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    jsonl_path = out_dir / f"{stamp}-{mode}-runs.jsonl"
    summary_path = out_dir / f"{stamp}-{mode}-summary.json"

    server = start_server()
    port = server.server_address[1]
    records = []
    with sync_playwright() as p, jsonl_path.open("w", encoding="utf-8") as out:
        browser = p.chromium.launch(headless=True)
        for task in suite["tasks"]:
            base = json.loads((suite_path.parent / task["plan"]).read_text(encoding="utf-8"))
            for layout in task["layouts"]:
                plan = with_layout(point_at(base, port), layout)
                if mode == "fake":
                    check, repair = always_ok, oracle_repair(task.get("oracle_fixes", {}).get(layout, {}))
                else:
                    check, repair = model_check, model_repair
                for run in range(1, runs + 1):
                    started_at = datetime.now().astimezone().isoformat(timespec="seconds")
                    run_info = {"layout": layout, "models": models}
                    record = {"mode": mode, "note": note, "task": task["id"], "layout": layout, "run": run,
                              "models": models, "started_at": started_at,
                              **run_one(browser, plan, check, repair, task["done_when"], run_info)}
                    records.append(record)
                    # Written line by line so a crash in a long model run keeps the finished runs.
                    out.write(json.dumps(record) + "\n")
                    out.flush()
        browser.close()
    server.shutdown()
    server.server_close()

    summary = {"mode": mode, "note": note, "models": models, "runs_per_layout": runs,
               "tasks_filter": tasks, "layouts_filter": layouts, "raw": jsonl_path.name, **summarize(records)}
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return records, summary, jsonl_path, summary_path


def print_table(summary):
    def fmt(v):
        return "-" if v is None else str(v)
    print(summary["note"])
    print(f"{'task':<24}{'layout':<8}{'runs':>5}{'success':>9}{'repair ok':>11}{'steps/task':>12}{'s/step':>9}")
    for row in summary["by_task_layout"] + [{"task": "ALL", "layout": "", **summary["overall"]}]:
        print(f"{row['task']:<24}{row['layout']:<8}{row['runs']:>5}{fmt(row['task_success_rate']):>9}"
              f"{fmt(row['repair_success_rate']):>11}{fmt(row['steps_per_task']):>12}{fmt(row['time_per_step_s']):>9}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["fake", "gemma"], required=True)
    parser.add_argument("--runs", type=int, default=1, help="runs per task and layout")
    parser.add_argument("--out", type=Path, default=RESULTS)
    parser.add_argument("--tasks", nargs="+", help="task ids to run (default: all)")
    parser.add_argument("--layouts", nargs="+", help="layout ids to run (default: each task's own list)")
    args = parser.parse_args()
    try:
        _, summary, jsonl_path, summary_path = run_suite(args.mode, args.runs, args.out,
                                                         tasks=args.tasks, layouts=args.layouts)
    except (llm.LLMError, ValueError) as e:
        print(e, file=sys.stderr)
        return 2
    print_table(summary)
    print(f"raw: {jsonl_path}\nsummary: {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
