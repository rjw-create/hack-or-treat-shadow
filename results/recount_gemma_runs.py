"""Recount Gemma eval results from raw JSONL, independently of the runner's own counters.

Usage (from the repo root):
  python results/recount_gemma_runs.py results/<stamp>-gemma-runs.jsonl [...]

Repairs are counted from each step's attempts: a repair succeeded if the next attempt's action ran and its
check said ok. The script then compares these counts with the runner's `repairs_attempted` /
`repairs_succeeded` fields and with any matching `-summary.json`, and exits 1 on a mismatch.
"""
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path


def recount_run(record):
    attempted = succeeded = 0
    repaired_step_times_s = []
    repair_times_s = []
    for step in record["run_log"]["steps"]:
        attempts = step["attempts"]
        step_had_repair = False
        for i, attempt in enumerate(attempts):
            repair = attempt.get("repair")
            if not repair:
                continue
            attempted += 1
            step_had_repair = True
            repair_times_s.append(repair["repair_s"])
            nxt = attempts[i + 1] if i + 1 < len(attempts) else None
            if nxt and nxt["action_ok"] and (nxt.get("check") or {}).get("ok"):
                succeeded += 1
        if step_had_repair:
            repaired_step_times_s.append(step["time_s"])
    return attempted, succeeded, repaired_step_times_s, repair_times_s


def mean(values):
    return round(statistics.mean(values), 1) if values else None


def main(paths):
    groups = defaultdict(lambda: {"runs": 0, "success": 0, "attempted": 0, "succeeded": 0,
                                  "step_times_s": [], "repair_s": [], "time_per_step_s": []})
    mismatches = []
    for path in map(Path, paths):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            record = json.loads(line)
            attempted, succeeded, step_times_s, repair_s = recount_run(record)
            where = f"{path.name}:{line_no}"
            if (attempted, succeeded) != (record["repairs_attempted"], record["repairs_succeeded"]):
                mismatches.append(f"{where}: recount {succeeded}/{attempted}, runner "
                                  f"{record['repairs_succeeded']}/{record['repairs_attempted']}")
            success = record["task_success"] and record["ok"] and record["end_state_ok"]
            if success != record["task_success"]:
                mismatches.append(f"{where}: task_success true but ok/end_state_ok false")
            g = groups[(record["task"], record["layout"])]
            g["runs"] += 1
            g["success"] += success
            g["attempted"] += attempted
            g["succeeded"] += succeeded
            g["step_times_s"] += step_times_s
            g["repair_s"] += repair_s
            g["time_per_step_s"].append(record["time_per_step_s"])
            print(f"{where} {record['task']} {record['layout']} run {record['run']}: "
                  f"success={success} repairs {succeeded}/{attempted} repaired-step time_s={step_times_s} "
                  f"repair_s={repair_s} duration_s={record['duration_s']}")

        summary_path = path.with_name(path.name.replace("-runs.jsonl", "-summary.json"))
        if summary_path.exists():
            for row in json.loads(summary_path.read_text(encoding="utf-8"))["by_task_layout"]:
                g = groups[(row["task"], row["layout"])]
                if (row["repairs_succeeded"], row["repairs_attempted"]) != (g["succeeded"], g["attempted"]):
                    mismatches.append(f"{summary_path.name}: {row['task']} {row['layout']} repairs differ")
                if round(row["task_success_rate"] * row["runs"]) != g["success"]:
                    mismatches.append(f"{summary_path.name}: {row['task']} {row['layout']} success differs")

    print()
    print("| Task | Layout | Task success | Repairs (succeeded / attempted) | Mean `time_s` of repaired step "
          "| Mean `repair_s` | Mean time per step |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for (task, layout), g in sorted(groups.items()):
        print(f"| {task} | {layout} | {g['success']} / {g['runs']} | {g['succeeded']} / {g['attempted']} "
              f"| {mean(g['step_times_s'])} s | {mean(g['repair_s'])} s | {mean(g['time_per_step_s'])} s |")
    print()
    if mismatches:
        print("MISMATCHES:\n" + "\n".join(mismatches))
        return 1
    print("All recounts match the runner's saved counts.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
