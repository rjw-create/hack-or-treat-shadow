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

## Checks (Git Bash)
```
./scripts/check.sh
```

## Limits
- The recorder's role and name detection is a simplified version of the ARIA rules; it covers standard form controls.
- A retry after a failed check can repeat an action (checkboxes use `check()` to avoid toggling twice).
- Only browser tasks on localhost pages.
