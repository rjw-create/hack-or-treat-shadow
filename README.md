# Shadow

Record yourself doing a browser task once. Shadow turns the recording into a step plan with local
Gemma 4, runs it, checks each step, and repairs the plan when the page changes.
Nothing leaves your machine.

**Live demo:** https://rjw-create.github.io/hack-or-treat-shadow/demo/ shows recorded real runs: the video and the
report for each layout. Shadow itself runs locally with Ollama; the demo page does not call a model.
Video only: https://rjw-create.github.io/hack-or-treat-shadow/demo/shadow-backup.mp4 (77 s, model waits sped up,
real speed shown on screen).

## How it works
1. `shadow.record` opens a browser and logs each click, fill and select by its role and accessible
   name (for example `button "Export selected"`), plus a screenshot after each event.
2. `shadow.plan` sends the event log and a few screenshots to the planner model. It returns a JSON plan:
   each step has an intent, one action from a fixed list (`goto click fill select press`), a target and
   the expected page state. Shadow validates the plan; the model never writes code.
3. `shadow.run` performs each step and the checker model confirms the expected state. Routine steps are
   checked against the page's accessibility tree as text, which is faster; the final step and the step right
   after a repair are checked against a screenshot. Checks run with Gemma 4's thinking turned off. If a step fails, the planner gets the page's accessibility tree and returns a patched step.
4. `shadow.compile` turns a plan into a readable Playwright script.

The runner only visits `localhost` URLs.

## Setup (PowerShell)
```
py -3.11 -m venv .venv
```
```
.venv\Scripts\python -m pip install playwright
```
```
.venv\Scripts\python -m playwright install chromium
```
On Windows PowerShell 5.1, pip's "new release available" notice can show up in red. It is harmless.

Install [Ollama](https://ollama.com), then pull the model. Shadow was tested with `gemma4:e4b` as both planner
and checker:
```
ollama pull gemma4:e4b
```

## Demo
Terminal 1, from the project folder: serve the fake invoice app and leave it running.
```
.venv\Scripts\python -m http.server 8000
```
Terminal 2, from the project folder. Set the model tags **in this terminal**: `$env:` variables only exist in
the terminal that set them.
```
$env:SHADOW_PLANNER_MODEL = "gemma4:e4b"; $env:SHADOW_CHECKER_MODEL = "gemma4:e4b"
```
Check the setup and load the model now, so the first step isn't slow. It prints `Ready: loaded ...`, or one line
saying what to fix:
```
.venv\Scripts\python -m shadow.warmup
```
Record the task. Do it in the browser window that opens, then close the window. The last line reads
`Saved N events to runs\<recording id>`; use that folder name below.
```
.venv\Scripts\python -m shadow.record http://localhost:8000/demo_site/invoices.html
```
```
.venv\Scripts\python -m shadow.plan runs\<recording id>
```
```
.venv\Scripts\python -m shadow.run runs\<recording id>\plan.json --layout b
```
`--layout b` moves the export button and renames it to "Download selected", so the recorded step fails and
has to be repaired. The run ends with `Run log: runs\<recording id>\exec\<exec id>\run.json`.

### Demo without recording first
Use the example plan instead. Copy it into `runs\` (git-ignored) rather than running it in place, because the
runner writes its results next to the plan. Same terminal 2, with the model variables set:
```
New-Item -ItemType Directory -Force runs\demo
```
```
Copy-Item tests\fixtures\plan_export.json runs\demo\plan.json
```
```
.venv\Scripts\python -m shadow.run runs\demo\plan.json --layout b
```

### Layout variants
The demo page reads `?layout=<id>` (the runner adds it from `--layout`). A missing or unknown id gives the normal
layout. Each variant breaks a different kind of locator:

| Layout | What changes | Recorded step that breaks |
| --- | --- | --- |
| `a` | Nothing (normal layout) | None |
| `b` | Export button renamed "Download selected" and moved below the table | click button "Export selected" |
| `c` | Labels renamed "Find client" and "Payment status" | fill searchbox "Search customer", select combobox "Status" |
| `d` | Row checkboxes renamed "Include INV-...", button renamed "Export invoices" | click checkbox "Select INV-...", click button "Export selected" |
| `e` | Status dropdown replaced by radio buttons | select combobox "Status"; the repair has to change the action to click radio "Unpaid" |

### Run report
Each run writes `run.json` (format in `docs/interface.md`) in the folder named on its `Run log:` line. Pass that
folder, without `\run.json`, to the viewer:
```
.venv\Scripts\python -m viewer.report runs\<recording id>\exec\<exec id>
```
This writes `report.html` in the same folder; open it straight from disk. It shows a summary, then each step with
its screenshot, a box around the element the step acted on, the checker's verdict (labelled text or screenshot
check) and the time taken. A repaired step shows the planner's explanation, the old target next to the new one,
and the failed and repaired screenshots side by side. All model-written text is escaped, and the page has no
JavaScript.

To see a report without a model, use the hand-made example run, then open
`viewer\fixtures\repaired_run\report.html`:
```
.venv\Scripts\python -m viewer.report viewer\fixtures\repaired_run
```

## Evals
`evals/run_evals.py` runs every task in `evals/suite.json` on layouts `a` to `e` and writes raw results and a
summary to `results/`:
```
.venv\Scripts\python -m evals.run_evals --mode fake
```
```
.venv\Scripts\python -m evals.run_evals --mode gemma --runs 3
```
`--mode fake` is a pipeline test: its checker always says ok and its repairer already knows the answer.
Evals write only `results\` by default. Add `--show` for a visible browser, the runner's log on the console, and a
run folder per run (path printed as `Run folders go to ...`) that `viewer.report` can read. `--tasks` and
`--layouts` pick a subset, for example `--tasks export_invoice --layouts a b e`.

## Results
Real runs with `gemma4:e4b` as planner and checker on a laptop CPU:
- 2026-10-31: task `export_invoice`, one run on each of layouts a, b and e. Details:
  [`results/2026-10-31-gemma-run-notes.md`](results/2026-10-31-gemma-run-notes.md).
- 2026-11-03 and 2026-11-04: all three suite tasks (`export_invoice`, `export_all_unpaid_acme`,
  `export_paid_initech`) on layouts f, g and h, 3 runs per task and layout (27 runs). Details:
  [`results/2026-11-03-page-change-run-notes.md`](results/2026-11-03-page-change-run-notes.md) and
  [`results/2026-11-04-remaining-tasks-run-notes.md`](results/2026-11-04-remaining-tasks-run-notes.md).

**30 of 30 tasks succeeded, and 29 of 29 repairs worked on the first try.** Task success means the runner reported
success and the page showed the expected end state. These are too few runs for a general success rate (see Limits).

| Layout | What changed on the page | Task success | Repairs that worked on the first try | Mean repair time (model call) |
| --- | --- | --- | --- | --- |
| f | Search label renamed "Filter by company" | 9 of 9 | 9 of 9 | 36.5 s |
| g | Export button moved next to the page title and renamed "Export" | 9 of 9 | 9 of 9 | 31.6 s |
| h | Status dropdown replaced by radio buttons "All", "Settled", "Outstanding" | 9 of 9 | 9 of 9 | 57.0 s |

- **Layouts a, b and e (2026-10-31):** 3 of 3 tasks succeeded and 2 of 2 repairs worked on the first try. Layout b:
  "Export selected" became "Download selected". Layout e: Gemma 4 changed the step's action, from `select` on the
  Status dropdown to `click` on the "Unpaid" radio button.
- **Layout h:** Gemma 4 picked the radio button by meaning: "Outstanding" for the two unpaid tasks and "Settled"
  for the paid task.
- **Time:** 30.2 s per step on average on 2026-10-31, almost all of it model time (a 5-step task took 2.0 to 2.9
  minutes), and 20.0 s per step on layouts f, g and h. The 2026-10-31 runs used a visible browser recording video;
  the later runs were headless, so the per-step times are not strictly comparable.
- **Earlier run:** before Core's checker and timeout fixes, layout b's repair was also right, but the screenshot
  checker contradicted itself and the runner gave up. The notes compare both runs.

The `fake` files in `results/` are pipeline tests; they say nothing about how well Gemma 4 plans, checks or repairs.

## Checks (Git Bash)
```
./scripts/check.sh
```

## Limits
- The recorder's role and name detection is a simplified version of the ARIA rules; it covers standard form controls.
- A retry after a failed check can repeat an action (checkboxes use `check()` to avoid toggling twice).
- Only browser tasks on localhost pages.
- The demo site is a small fake invoice app with eight layouts; real sites will change in more ways than these.
- 29 repairs on one demo app are too few for a general success rate. Layouts a, b and e have one run each;
  layouts f, g and h have 3 runs per task.
- The report's target box relies on the runner's device scale factor of 1 (1 CSS pixel per screenshot pixel).

## License
Apache License 2.0. See [`LICENSE`](LICENSE).
