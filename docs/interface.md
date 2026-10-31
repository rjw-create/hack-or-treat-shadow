# Shadow interface (owned by Core)

Surface and Proof build against this file. Only Core changes it, and every change is called out in the
PR description (see `2026-10-31-ROLES.md`).

**Status:** all three formats are implemented: `events.jsonl` (`shadow/record.py`), `plan.json`
(`shadow/steps.py`) and `run.json` (`shadow/run.py`, `run_plan()` and `save_run()`).
`tests/test_run_fake.py::test_run_log_matches_interface` checks `run.json` against this file.

## Conventions
- All files are UTF-8 JSON. Durations are seconds with an `_s` suffix (`check_s`, `time_per_step_s`).
- Timestamps are ISO 8601 local time with UTC offset, e.g. `2026-10-31T15:30:02-04:00`.
- Paths inside a file are relative to the folder that file is in, with forward slashes.
- Step numbers (`index`, `failed_step`) start at 1.
- Adding a field is not a breaking change: readers must ignore fields they don't know.
  Renaming or removing a field, or changing its meaning, bumps `schema_version` in `run.json`.

## Folder layout
```
runs/<recording_id>/              recording_id = YYYY-MM-DD_HHMMSS when recording started
  events.jsonl                    what the person did           (shadow.record)
  shots/000.png ...               screenshot after each event   (shadow.record)
  plan.json                       plan made from the recording  (shadow.plan)
  exec/<exec_id>/                 one per run of the plan; exec_id = YYYY-MM-DD_HHMMSS
    run.json                      the run log                   (shadow.run)
    shots/<index>-<attempt>.png   screenshot after each attempt, e.g. 005-2.png
    plan.repaired.json            only if a repair happened
    automation.py                 compiled Playwright script of the final plan
```
`runs/` is git-ignored because screenshots can show anything on screen. Fixtures for tests or the viewer
are hand-made copies placed in your own folder.

## events.jsonl (recorder output)
One JSON object per line, in the order things happened. The first line is always the `goto` that opened the page.

| Field | Type | Meaning |
| --- | --- | --- |
| `type` | `"goto" \| "click" \| "fill" \| "select" \| "press"` | What the person did |
| `role` | string or null | ARIA role of the element (`button`, `checkbox`, `searchbox`, `combobox`, `textbox`, `link`, ...); null for `goto` |
| `name` | string or null | Accessible name, e.g. `"Export selected"`; null for `goto` |
| `value` | string or null | URL for `goto`, typed text for `fill`, option label for `select`, key for `press` (`"Enter"`) |
| `url` | string | Page URL when it happened |
| `t_s` | number | Seconds since recording started |
| `shot` | string or null | Screenshot path, e.g. `"shots/003.png"` |

## plan.json (planner output, runner input)
```json
{
  "task": "Export the latest unpaid Acme Corp invoice",
  "steps": [ { "intent": "...", "action": "...", "target": {"role": "...", "name": "..."}, "value": "...", "expected": "..." } ]
}
```
| Field | Required | Meaning |
| --- | --- | --- |
| `task` | yes | One sentence describing the whole job |
| `steps[].intent` | yes | What the step is for, in plain words ("Pick the latest invoice") |
| `steps[].action` | yes | One of `goto`, `click`, `fill`, `select`, `press`. Nothing else is accepted. |
| `steps[].target` | for `click fill select press` | `{role, name}`; the runner finds it with `get_by_role(role, name=name, exact=True)` |
| `steps[].value` | for `goto fill select press` | URL, text, option label, or key |
| `steps[].expected` | yes | What the page should show right after the step; the checker judges a screenshot against it |

Rules enforced by `shadow/steps.py`: `goto` URLs must be `http(s)://localhost` or `127.0.0.1`. A `click` on a
`checkbox` or `radio` is performed as "make sure it is ticked", so repeating it is safe.
A working example is `tests/fixtures/plan_export.json`.

**Layout variants (demo site contract):** the runner selects a variant by setting the `layout` query
parameter on every `goto` URL (`--layout b` gives `...invoices.html?layout=b`). A demo page treats a
missing or unknown `layout` as its normal layout. Layout ids are 1 to 20 characters from `a-z`, `0-9`
and `-`; `--layout` accepts any such id. Without `--layout` the plan's URLs are used unchanged and
`run.json` has `"layout": null`.

**Running without a model (Proof, Surface):** call `shadow.run.run_plan(page, plan, check=..., repair=...,
shots_dir=..., run_info=...)` with plain functions `check(page, step) -> (ok, reason)` and
`repair(page, step, problem) -> (new_step, explanation)`, then `save_run(exec_dir, result)`.
`tests/test_run_fake.py` shows the pattern.

## run.json (runner output, schema_version 1)
Top level:

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | `1` | Bumped on breaking changes |
| `recording_id`, `exec_id` | string | Folder names from the layout above; `recording_id` is null if the plan was not made from a recording |
| `task` | string | Copied from the plan |
| `layout` | string or null | Layout id passed to the runner |
| `models` | `{planner, checker}` | Ollama model tags used, or `"fake"` in tests |
| `started_at` | timestamp | When the run started |
| `duration_s` | number | Wall time of the whole run |
| `ok` | boolean | True if every step passed |
| `failed_step` | integer or null | Index of the step the run gave up on |
| `steps` | array | One entry per plan step, in order, including steps never reached |
| `summary` | object | Totals, below |

Each `steps[]` entry:

| Field | Type | Meaning |
| --- | --- | --- |
| `index` | integer | 1-based |
| `status` | `"passed" \| "repaired" \| "failed" \| "not_run"` | `repaired` = passed after at least one repair |
| `planned` | step object | The step as it was in the input plan |
| `time_s` | number | Total time for this step: all attempts, checks and repairs; 0 if `not_run` |
| `attempts` | array | Empty if `not_run` |

Each `attempts[]` entry:

| Field | Type | Meaning |
| --- | --- | --- |
| `attempt` | integer | 1-based; at most 3 (first try plus 2 repairs) |
| `step` | step object | The step actually performed in this attempt |
| `action_ok` | boolean | False if Playwright could not do the action (e.g. element not found) |
| `error` | string or null | First line of the Playwright error |
| `check` | `{ok, reason}` or null | Checker verdict; null if the action failed, so no check ran |
| `screenshot` | string or null | e.g. `"shots/005-1.png"`, taken after the action and before the check |
| `bbox` | `{x, y, width, height}` or null | Where the step's target is in `screenshot`, in CSS pixels from the top-left of the viewport, measured right after the action. Null for `goto`, failed actions, or if the element can't be found within 0.5 s. Optional for readers: draw it if present. |
| `action_s`, `check_s` | number | Time for the action and for the checker call (0 if not run) |
| `repair` | object or null | Present when this attempt failed and a repair was requested: `{explanation, new_step, accepted, repair_s}`. `accepted` is false if the repaired step failed validation. |

`summary`:

| Field | Meaning |
| --- | --- |
| `steps_total` | Number of steps in the plan |
| `steps_passed` | Steps with status `passed` or `repaired` |
| `repairs_attempted` | Number of `repair` objects across all attempts |
| `repairs_succeeded` | Repairs whose next attempt passed |
| `time_per_step_s` | Mean `time_s` over steps that ran (not `not_run`) |

Text fields written by the model (`intent`, `expected`, `check.reason`, `repair.explanation`, target names)
are untrusted. Anything that displays them must escape them (e.g. `textContent`, `html.escape`).

## Example run.json (layout b, one repair)
```json
{
  "schema_version": 1,
  "recording_id": "2026-10-31_151200",
  "exec_id": "2026-10-31_153002",
  "task": "Export the latest unpaid Acme Corp invoice",
  "layout": "b",
  "models": {"planner": "fake", "checker": "fake"},
  "started_at": "2026-10-31T15:30:02-04:00",
  "duration_s": 41.8,
  "ok": true,
  "failed_step": null,
  "steps": [
    {"index": 1, "status": "passed", "time_s": 6.2,
     "planned": {"intent": "Open the invoice list", "action": "goto", "value": "http://localhost:8000/demo_site/invoices.html?layout=b", "expected": "The Invoices page with a table of invoices"},
     "attempts": [{"attempt": 1, "step": {"intent": "Open the invoice list", "action": "goto", "value": "http://localhost:8000/demo_site/invoices.html?layout=b", "expected": "The Invoices page with a table of invoices"},
                   "action_ok": true, "error": null, "check": {"ok": true, "reason": "Invoice table is visible"},
                   "screenshot": "shots/001-1.png", "action_s": 0.5, "check_s": 5.7, "repair": null}]},
    {"index": 5, "status": "repaired", "time_s": 19.4,
     "planned": {"intent": "Export the selected invoice", "action": "click", "target": {"role": "button", "name": "Export selected"}, "expected": "A message says 1 invoice INV-1042 was exported"},
     "attempts": [
       {"attempt": 1, "step": {"intent": "Export the selected invoice", "action": "click", "target": {"role": "button", "name": "Export selected"}, "expected": "A message says 1 invoice INV-1042 was exported"},
        "action_ok": false, "error": "Locator.click: Timeout 3000ms exceeded.", "check": null,
        "screenshot": "shots/005-1.png", "action_s": 3.0, "check_s": 0,
        "repair": {"explanation": "The Export button was renamed to Download selected and moved below the table.",
                   "new_step": {"intent": "Export the selected invoice", "action": "click", "target": {"role": "button", "name": "Download selected"}, "expected": "A message says 1 invoice INV-1042 was exported"},
                   "accepted": true, "repair_s": 10.1}},
       {"attempt": 2, "step": {"intent": "Export the selected invoice", "action": "click", "target": {"role": "button", "name": "Download selected"}, "expected": "A message says 1 invoice INV-1042 was exported"},
        "action_ok": true, "error": null, "check": {"ok": true, "reason": "Status line reads Exported 1 invoice: INV-1042"},
        "screenshot": "shots/005-2.png", "action_s": 0.2, "check_s": 6.1, "repair": null}
     ]}
  ],
  "summary": {"steps_total": 5, "steps_passed": 5, "repairs_attempted": 1, "repairs_succeeded": 1, "time_per_step_s": 8.4}
}
```
Steps 2 to 4 are left out of the example for length; a real `run.json` lists every step.
The numbers in the example are made up to show the format, not measurements.
