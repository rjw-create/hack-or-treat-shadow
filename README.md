# Shadow

Record yourself doing a browser task once. Shadow turns the recording into a step plan with local
Gemma 4, runs it, checks each step against a screenshot, and repairs the plan when the page changes.
Nothing leaves your machine.

## How it works
1. `shadow.record` opens a browser and logs each click, fill and select by its role and accessible
   name (for example `button "Export selected"`), plus a screenshot after each event.
2. `shadow.plan` sends the event log and a few screenshots to the planner model. It returns a JSON plan:
   each step has an intent, one action from a fixed list (`goto click fill select press`), a target and
   the expected page state. Shadow validates the plan; the model never writes code.
3. `shadow.run` performs each step. The checker model looks at a screenshot and confirms the expected
   state. If a step fails, the planner gets the page's accessibility tree and returns a patched step.
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
Install Ollama, pull the Gemma 4 models, then set the tags you pulled:
```
$env:SHADOW_PLANNER_MODEL = "<planner tag from ollama list>"; $env:SHADOW_CHECKER_MODEL = "<checker tag>"
```

## Demo
Serve the fake invoice app from the project folder:
```
.venv\Scripts\python -m http.server 8000
```
Then, in a second terminal:
```
.venv\Scripts\python -m shadow.record http://localhost:8000/demo_site/invoices.html
```
```
.venv\Scripts\python -m shadow.plan runs\<run id>
```
```
.venv\Scripts\python -m shadow.run runs\<run id>\plan.json --layout b
```
`--layout b` moves the export button and renames it to "Download selected", so the recorded step fails and
has to be repaired.

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
Each run writes `runs\<run id>\exec\<exec id>\run.json` (format in `docs/interface.md`). Turn it into a page:
```
.venv\Scripts\python -m viewer.report runs\<run id>\exec\<exec id>
```
This writes `report.html` in the same folder; open it straight from disk. It shows a summary, then each step with
its screenshot, a box around the element the step acted on, the checker's verdict and the time taken. A repaired
step shows the planner's explanation, the old target next to the new one, and the failed and repaired screenshots
side by side. All model-written text is escaped, and the page has no JavaScript.

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

## Results
No results from Gemma 4 yet. The files in `results/` so far are fake-mode pipeline tests; they show the runner,
repair loop and metrics work end to end, and say nothing about how well Gemma 4 plans, checks or repairs.
This section will list task success rate, repair success rate and time per step from `--mode gemma` runs, with a
link to the raw file each number comes from.

Measured time per step with Gemma 4 on this machine: (fill in from the first real run)

## Checks (Git Bash)
```
./scripts/check.sh
```

## Limits
- The recorder's role and name detection is a simplified version of the ARIA rules; it covers standard form controls.
- A retry after a failed check can repeat an action (checkboxes use `check()` to avoid toggling twice).
- Only browser tasks on localhost pages.
- The demo site is a small fake invoice app with five layouts; real sites will change in more ways than these.
- The report's target box assumes the runner's default device scale factor (1 CSS pixel per screenshot pixel).
