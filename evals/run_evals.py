"""Eval suite: every task x layout x run, one raw JSONL line each, plus a summary.

Usage (from the repo root):
  python -m evals.run_evals --mode fake             pipeline test, no model
  python -m evals.run_evals --mode gemma --runs 3   real Gemma 4 through Ollama (SHADOW_*_MODEL)

Fake mode is a pipeline test only: the checker always says ok and the repairer is an oracle that
already knows the answer. Its numbers say nothing about Gemma's ability.

Metrics are built from the run_plan() return value and its log lines, because run.json is not
written by the runner yet. Switch to run.json once Core ships it.
"""
import argparse
import copy
import functools
import http.server
import json
import re
import statistics
import sys
import threading
import time
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
# run_plan logs "[i/n] intent" at the start of every attempt; this is how steps are timed.
STEP_START = re.compile(r"^\[(\d+)/\d+\]")


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


def oracle_repair(renames):
    """Fake repairer that knows which target names changed in this layout."""
    def repair(page, step, problem):
        fixed = copy.deepcopy(step)
        target = fixed.get("target")
        if target and target.get("name") in renames:
            target["name"] = renames[target["name"]]
            return fixed, f"Oracle: {step['target']['name']} is now {target['name']}."
        return fixed, "Oracle has no fix for this step."
    return repair


def end_state_ok(page, done_when):
    """Ground truth read from the page itself, independent of the checker model."""
    try:
        text = page.get_by_role(done_when["role"]).first.text_content(timeout=END_STATE_TIMEOUT_MS)
    except PlaywrightError:
        return False
    return (text or "").strip() == done_when["text"]


def run_one(browser, plan, check, repair, done_when):
    """Run one plan in a fresh page and return its raw metrics."""
    marks = []         # (step index, perf_counter) each time the runner starts an attempt
    repair_calls = {}  # step index -> repairs requested for it

    def log(msg):
        m = STEP_START.match(msg)
        if m:
            marks.append((int(m.group(1)), time.perf_counter()))

    def counted_repair(page, step, problem):
        i = marks[-1][0]
        repair_calls[i] = repair_calls.get(i, 0) + 1
        return repair(page, step, problem)

    page = browser.new_page()
    error = None
    t0 = time.perf_counter()
    try:
        result = run_plan(page, plan, check=check, repair=counted_repair, log=log)
    except Exception as e:  # e.g. Ollama down or bad JSON: end this run, keep the suite going
        first_line = str(e).splitlines()[0] if str(e) else ""
        error = f"{type(e).__name__}: {first_line}"
        result = {"ok": False, "repairs": [], "failed_step": marks[-1][0] if marks else 1}
    t_end = time.perf_counter()
    end_ok = end_state_ok(page, done_when)
    page.close()

    starts, attempts = {}, {}
    for i, t in marks:
        starts.setdefault(i, t)
        attempts[i] = attempts.get(i, 0) + 1
    order = sorted(starts)
    step_times = []
    for n, i in enumerate(order):
        end = starts[order[n + 1]] if n + 1 < len(order) else t_end
        step_times.append(round(end - starts[i], 3))

    steps_total = len(plan["steps"])
    steps_passed = steps_total if result["ok"] else result["failed_step"] - 1
    # A step that passed after k repairs had one successful repair (the last); a failed step had none.
    repairs_succeeded = sum(1 for i in repair_calls if i <= steps_passed)
    return {
        "ok": result["ok"],
        "end_state_ok": end_ok,
        "task_success": result["ok"] and end_ok,
        "failed_step": result["failed_step"],
        "error": error,
        "steps_total": steps_total,
        "steps_run": len(order),
        "steps_passed": steps_passed,
        "attempts": len(marks),
        "attempts_per_step": [attempts[i] for i in order],
        "repairs_attempted": sum(repair_calls.values()),
        "repairs_accepted": len(result["repairs"]),
        "repairs_succeeded": repairs_succeeded,
        "duration_s": round(t_end - t0, 3),
        "step_times_s": step_times,
        "time_per_step_s": round(statistics.mean(step_times), 3) if step_times else None,
        "repairs": result["repairs"],
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


def run_suite(mode, runs, out_dir, suite_path=SUITE):
    """Run the whole suite; returns (records, summary, jsonl_path, summary_path)."""
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
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
                    check, repair = always_ok, oracle_repair(task.get("oracle_renames", {}).get(layout, {}))
                else:
                    check, repair = model_check, model_repair
                for run in range(1, runs + 1):
                    started_at = datetime.now().astimezone().isoformat(timespec="seconds")
                    record = {"mode": mode, "note": note, "task": task["id"], "layout": layout, "run": run,
                              "models": models, "started_at": started_at,
                              **run_one(browser, plan, check, repair, task["done_when"])}
                    records.append(record)
                    # Written line by line so a crash in a long model run keeps the finished runs.
                    out.write(json.dumps(record) + "\n")
                    out.flush()
        browser.close()
    server.shutdown()
    server.server_close()

    summary = {"mode": mode, "note": note, "models": models, "runs_per_layout": runs,
               "raw": jsonl_path.name, **summarize(records)}
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return records, summary, jsonl_path, summary_path


def print_table(summary):
    def fmt(v):
        return "-" if v is None else str(v)
    print(summary["note"])
    print(f"{'task':<18}{'layout':<8}{'runs':>5}{'success':>9}{'repair ok':>11}{'steps/task':>12}{'s/step':>9}")
    for row in summary["by_task_layout"] + [{"task": "ALL", "layout": "", **summary["overall"]}]:
        print(f"{row['task']:<18}{row['layout']:<8}{row['runs']:>5}{fmt(row['task_success_rate']):>9}"
              f"{fmt(row['repair_success_rate']):>11}{fmt(row['steps_per_task']):>12}{fmt(row['time_per_step_s']):>9}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["fake", "gemma"], required=True)
    parser.add_argument("--runs", type=int, default=1, help="runs per task and layout")
    parser.add_argument("--out", type=Path, default=RESULTS)
    args = parser.parse_args()
    try:
        _, summary, jsonl_path, summary_path = run_suite(args.mode, args.runs, args.out)
    except llm.LLMError as e:
        print(e, file=sys.stderr)
        return 2
    print_table(summary)
    print(f"raw: {jsonl_path}\nsummary: {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
