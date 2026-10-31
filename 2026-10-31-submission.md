# Shadow: submission text

Hack or Treat 2026, category: Best use of Gemma 4. Draft; fill the bracketed parts after real Gemma 4 runs.

## One line
Show Shadow a browser task once; local Gemma 4 turns it into a plan, checks every step against a screenshot,
and repairs the plan when the page changes.

## What it does
Browser automations break when a page changes: a button is renamed, a dropdown becomes radio buttons, a label is
reworded. Shadow learns a task from one recorded demonstration and keeps it working through changes like these.

1. **Record.** You do the task once in a browser. Shadow logs each action by the element's role and accessible
   name (for example button "Export selected") and takes a screenshot after each one.
2. **Plan.** Gemma 4 turns the recording and a few screenshots into a JSON plan. Each step has an intent, one
   action from a fixed list (goto, click, fill, select, press), a target, and what the page should show afterwards.
   Shadow validates the plan. The model never writes code.
3. **Run and check.** Shadow performs each step. Gemma 4 looks at a screenshot of the page and judges whether the
   expected state is there.
4. **Repair.** When a step fails, Gemma 4 gets the page's accessibility tree and the failed step, explains what
   changed, and returns a patched step. Shadow validates it and retries, up to two repairs per step.
5. **Report.** Each run produces a page that shows every step with its screenshot, a box around the element it
   acted on, the check verdict, and each repair with the old and new target.

## How Gemma 4 is used
- **Planner** (`SHADOW_PLANNER_MODEL`): writes the plan from the recording, and writes repairs. [tag used]
- **Checker** (`SHADOW_CHECKER_MODEL`): judges each step from a screenshot. [tag used]
- Both run locally through Ollama on a laptop with an Intel Arc 140V integrated GPU and 32 GB of shared RAM.

## Why local, open weights matter here
A recording of someone using a browser can show anything on their screen: customer names, invoices, messages.
Shadow sends those screenshots to a model on every step. With Gemma 4 running locally, the screenshots and
recordings stay on the machine (`runs/` is never committed), and the automation keeps working without a network
connection or a per-call bill.

## Safety choices
- The model only produces JSON from a fixed set of actions; Shadow validates every plan and every repair.
- The runner only visits `localhost` pages.
- All model-written text in the report is escaped.

## Results
[Fill in from `results/` after `python -m evals.run_evals --mode gemma`: task success rate, repair success rate,
steps per task and time per step on 3 tasks x 5 layouts, each with a link to the raw results file.]
The fake-mode files currently in `results/` are pipeline tests and are not model results.

## Limits
- Only localhost pages, and only the demo invoice app has been tested.
- Each checker call is a vision model call on a laptop, so runs are slow: [measured time per step].
- The recorder covers standard form controls, not every ARIA pattern.

## Links
- Code: https://github.com/rjw-create/hack-or-treat-shadow
- Demo video: [link after recording]
