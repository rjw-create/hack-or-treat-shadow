# Shadow: submission text

Hack or Treat 2026, category: Best use of Gemma 4. Ready to submit; the live demo and video links are under Links.

## One line
Show Shadow a browser task once; local Gemma 4 turns it into a plan, checks every step, and repairs the plan
when the page changes.

## What it does
Browser automations break when a page changes: a button is renamed, a dropdown becomes radio buttons, a label is
reworded. Shadow learns a task from one recorded demonstration and keeps it working through changes like these.

1. **Record.** You do the task once in a browser. Shadow logs each action by the element's role and accessible
   name (for example button "Export selected") and takes a screenshot after each one.
2. **Plan.** Gemma 4 turns the recording and a few screenshots into a JSON plan. Each step has an intent, one
   action from a fixed list (goto, click, fill, select, press), a target, and what the page should show afterwards.
   Shadow validates the plan. The model never writes code.
3. **Run and check.** Shadow performs each step and Gemma 4 judges whether the expected state is there. Routine
   steps are checked against the page's accessibility tree as text; the final step and any step right after a
   repair are checked against a screenshot, where a person would look.
4. **Repair.** When a step fails, Gemma 4 gets the page's accessibility tree and the failed step, explains what
   changed, and returns a patched step. Shadow validates it and retries, up to two repairs per step.
5. **Report.** Each run produces a page that shows every step with its screenshot, a box around the element it
   acted on, the check verdict, and each repair with the old and new target.

## How Gemma 4 is used
- **Planner** (`SHADOW_PLANNER_MODEL`): writes the plan from the recording, and writes repairs.
- **Checker** (`SHADOW_CHECKER_MODEL`): judges each step, from text for routine steps and from a screenshot for
  the final step and after a repair. Thinking is turned off for checks: on gemma4:e4b on this CPU it cut the mean
  check time from 46.8 s to 24.1 s with the same verdicts (6 of 6 correct either way; noted in `shadow/run.py`).
- Both roles used `gemma4:e4b` in the runs below.
- Both run locally through Ollama on a laptop with an Intel Arc 140V integrated GPU and 32 GB of shared RAM.

## Why local, open weights matter here
A recording of someone using a browser can show anything on their screen: customer names, invoices, messages.
Shadow sends page contents and screenshots to a model during every run. With Gemma 4 running locally, the screenshots and
recordings stay on the machine (`runs/` is never committed), and the automation keeps working without a network
connection or a per-call bill.

## Safety choices
- The model only produces JSON from a fixed set of actions; Shadow validates every plan and every repair.
- The runner only visits `localhost` pages.
- All model-written text in the report is escaped.

## Results
**30 of 30 tasks succeeded, and 29 of 29 repairs worked on the first try**, across two sets of real runs with
`gemma4:e4b` as planner and checker on a laptop CPU. These are too few runs for a general success rate (see Limits).

Task success means the runner reported success **and** the page shows the expected end state.

**2026-10-31: layouts a, b and e, one run each.** Task "export the latest unpaid Acme Corp invoice". Source:
`results/2026-10-31-gemma-run-notes.md` and the raw run logs it links
(`results/2026-10-31-140849-gemma-runs.jsonl`, `results/2026-10-31-141134-gemma-runs.jsonl`).

| Layout | Page change | Task success | Repair by Gemma 4 | Attempts per task | Mean time per step |
| --- | --- | --- | --- | --- | --- |
| a | none | yes | not needed | 5 | 24.2 s |
| b | Export button renamed and moved | yes | first try: "Export selected" became "Download selected" (33.4 s) | 6 | 31.1 s |
| e | Status dropdown became radio buttons | yes | first try: changed `select` to `click` on the "Unpaid" radio (53.4 s) | 6 | 35.1 s |

- **3 of 3 tasks succeeded, and 2 of 2 repairs worked on the first try.** On layout e, Gemma 4 changed the
  step's action, not just an element name.
- **The checker agreed with the page every time**, and the only failed actions were the two the layouts were
  built to break.
- **Time:** 30.2 s per step on average; a whole 5-step task took 2.0 to 2.9 minutes, almost all of it model time.
- Attempts count every try, retries included; each plan has 5 steps.

**2026-11-03 and 2026-11-04: layouts f, g and h, 3 runs per task and layout.** All three suite tasks
(`export_invoice`, `export_all_unpaid_acme`, `export_paid_initech`), 27 runs. Source:
`results/2026-11-03-page-change-run-notes.md` and `results/2026-11-04-remaining-tasks-run-notes.md`, recounted
from the raw run logs with `results/recount_gemma_runs.py`.

| Layout | Page change | Task success | Repairs that worked on the first try | Mean repair time (model call) |
| --- | --- | --- | --- | --- |
| f | Search label renamed "Filter by company" | 9 of 9 | 9 of 9 | 36.5 s |
| g | Export button moved next to the page title and renamed "Export" | 9 of 9 | 9 of 9 | 31.6 s |
| h | Status dropdown replaced by radio buttons "All", "Settled", "Outstanding" | 9 of 9 | 9 of 9 | 57.0 s |

- On layout h, Gemma 4 picked the radio button by meaning: "Outstanding" for the two unpaid tasks and "Settled"
  for the paid task.
- **Time:** 20.0 s per step on average. The 2026-10-31 runs used a visible browser recording video; these runs
  were headless, so the per-step times are not strictly comparable.

**Earlier run, before two fixes.** The first real run (same setup, earlier the same day) repaired both page
changes correctly too, but on layout b the screenshot checker said "not ok" on a correct page while its own
explanation said the page matched, and two unchanged elements hit a 3 s timeout, so the runner gave up. Core then
changed the checker to give one structured verdict with a text-check second opinion, told it the step has already
happened, and raised the action timeout to 10 s. Layout b then went from giving up after 814.7 s to passing in
155.6 s. Both runs are in the notes file above.

The fake-mode files in `results/` are pipeline tests and are not model results.

## Limits
- Only localhost pages, and only the demo invoice app has been tested.
- 29 repairs on one demo app are too few for a general success rate. Layouts a, b and e have one run each;
  layouts f, g and h have 3 runs per task.
- Every step waits for a model call on a laptop CPU: 20 to 30 s per step on average, and a 5-step task took 1.1 to
  3.8 minutes.
- The checker contradicted itself in the first run. The fixes removed that in the re-test, but 30 runs cannot
  rule it out.
- The recorder covers standard form controls, not every ARIA pattern.

## Links
- Code: https://github.com/rjw-create/hack-or-treat-shadow
- Live demo (recorded real runs: video and the three run reports; Shadow itself runs locally with Ollama):
  https://rjw-create.github.io/hack-or-treat-shadow/demo/
- Demo video (77 s, model waits sped up with the real speed shown on screen):
  https://rjw-create.github.io/hack-or-treat-shadow/demo/shadow-backup.mp4
