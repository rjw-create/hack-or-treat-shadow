# Real Gemma 4 runs: the other two tasks on layouts f, g and h (2026-11-04)

PR #28 ran only task `export_invoice` on the page-change layouts f, g and h
(`2026-11-03-page-change-run-notes.md`). These runs cover the other two suite tasks, `export_all_unpaid_acme` and
`export_paid_initech`, on the same three layouts, 3 runs each (18 runs). The suite now has 3 real runs for every
task on f, g and h (27 runs).

## How the runs were made
Same as PR #28: `gemma4:e4b` as planner and checker through Ollama on the same laptop, headless browser, model
loaded before timing started (the runner's warm-up). One task and one layout per command, 3 runs each, so that a
killed background command would lose at most one batch:

```
SHADOW_PLANNER_MODEL=gemma4:e4b SHADOW_CHECKER_MODEL=gemma4:e4b \
  python -m evals.run_evals --mode gemma --runs 3 --tasks <task> --layouts <layout>
```

All six batches finished; none was killed. Each batch was committed before the next started, so each one
records the previous batch's commit (`8d5a5cb` to `6071d0f`). Those commits differ only in `results/`, and every
batch has `dirty: false`.

| Task | Layout | Raw file (`-runs.jsonl` and `-summary.json`) |
| --- | --- | --- |
| export_all_unpaid_acme | f | `2026-11-04-161047-gemma` |
| export_all_unpaid_acme | g | `2026-11-04-161628-gemma` |
| export_all_unpaid_acme | h | `2026-11-04-162117-gemma` |
| export_paid_initech | f | `2026-11-04-162712-gemma` |
| export_paid_initech | g | `2026-11-04-163152-gemma` |
| export_paid_initech | h | `2026-11-04-163612-gemma` |

## Results (3 runs per task and layout)
| Task | Layout | Task success | Repairs (succeeded / attempted) | Mean `time_s` of the repaired step | Mean `repair_s` (model call only) | Mean time per step |
| --- | --- | --- | --- | --- | --- | --- |
| export_all_unpaid_acme | f | 3 / 3 | 3 / 3 | 54.8 s (83.0, 41.5, 40.0) | 33.0 s | 17.5 s |
| export_all_unpaid_acme | g | 3 / 3 | 3 / 3 | 46.6 s (63.4, 37.9, 38.5) | 27.2 s | 14.9 s |
| export_all_unpaid_acme | h | 3 / 3 | 3 / 3 | 68.9 s (76.4, 62.5, 68.0) | 48.1 s | 18.5 s |
| export_paid_initech | f | 3 / 3 | 3 / 3 | 55.2 s (66.8, 49.3, 49.4) | 34.9 s | 17.3 s |
| export_paid_initech | g | 3 / 3 | 3 / 3 | 51.8 s (68.0, 43.7, 43.7) | 32.7 s | 16.1 s |
| export_paid_initech | h | 3 / 3 | 3 / 3 | 91.9 s (102.3, 87.1, 86.3) | 71.2 s | 24.7 s |
| all 18 | | 18 / 18 | 18 / 18 | 61.5 s | 41.2 s | 18.2 s |

With PR #28's `export_invoice` runs, all three tasks on f, g and h (27 runs):

| Layout | Task success | Repairs | Mean `time_s` of the repaired step | Mean `repair_s` | Mean time per step |
| --- | --- | --- | --- | --- | --- |
| f | 9 / 9 | 9 / 9 | 59.0 s | 36.5 s | 19.6 s |
| g | 9 / 9 | 9 / 9 | 52.1 s | 31.6 s | 18.0 s |
| h | 9 / 9 | 9 / 9 | 79.4 s | 57.0 s | 23.0 s |
| all 27 | 27 / 27 | 27 / 27 | 63.5 s | 41.7 s | 20.2 s |

- Every repair worked on the first try, and each repaired step took 2 attempts. Every repair matched the
  suite's answer key (`oracle_fixes` in `evals/suite.json`):
  - f: `Search customer` became `Filter by company` (6 / 6).
  - g: `Export selected` became `Export` (6 / 6).
  - h: `select` on the Status combobox became `click` on a radio, and Gemma 4 picked the radio by meaning:
    `Outstanding` for the unpaid task (3 / 3) and `Settled` for the paid task (3 / 3). On h, a wrong radio would
    have listed the wrong invoices and failed the end-state check.
- Layout h's repairs are the slowest. For `export_paid_initech` on h the model call took 70.9 to 71.6 s in all
  three runs, against 44.7 to 52.6 s for `export_all_unpaid_acme` on h. The raw files don't show why.
- As in PR #28, the first run of each batch was slower: whole task 109.1 to 179.6 s for run 1, against 63.9 to
  108.0 s for runs 2 and 3. The raw files don't show why.
- Mean time per step is lower than for PR #28's `export_invoice` runs (18.2 s against 24.3 s). `export_paid_initech`
  has 5 steps like `export_invoice`, and `export_all_unpaid_acme` has 6. The raw files don't show why the per-step
  times differ, and these runs were made a day apart.
- Task success means the runner reported success and the page showed the task's `done_when` text
  (`Exported 2 invoices: INV-1041, INV-1042` or `Exported 1 invoice: INV-1043`).

## How the numbers were checked
`results/recount_gemma_runs.py` recomputes everything from the raw JSONL, separately from the runner's counters:
repairs are counted from each step's attempts (a repair succeeded if the next attempt's action ran and its check
said ok), then compared with each line's `repairs_attempted` / `repairs_succeeded` and with each batch's
`-summary.json`. It exits with an error on any mismatch. It matches all 18 new runs, and on PR #28's 9 runs it gives
PR #28's published numbers exactly.

```
python results/recount_gemma_runs.py results/2026-11-04-1*-gemma-runs.jsonl
```

The model was unloaded afterwards (`ollama stop gemma4:e4b`; `ollama ps` showed no loaded model).

## Caveat
These runs, like PR #28's, used a headless browser. The 2026-10-31 runs on layouts a, b and e were headed with page
video (`--show --video`), so per-step times are not strictly comparable between the two sets.
