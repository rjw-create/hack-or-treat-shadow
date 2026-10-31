# Shadow: submission text

Hack or Treat 2026, category: Best use of Gemma 4. Draft; the video link is still to fill in.

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
First real run: `gemma4:e4b` as planner and checker on a laptop CPU, task "export the latest unpaid Acme Corp
invoice", one run per layout. Three runs are an anecdote, not a measurement. Source:
`results/2026-10-31-gemma-run-notes.md` and the raw run logs it links.

Task success means the runner reported success **and** the page shows the expected end state.

| Layout | Page change | Task success | Repair of the changed element | Attempts per task | Mean time per step |
| --- | --- | --- | --- | --- | --- |
| a | none | yes | not needed | 5 | 24.7 s |
| e | Status dropdown became radio buttons | yes | correct on the first try: changed `select` to `click` on the "Unpaid" radio | 6 | 32.6 s |
| b | Export button renamed and moved | no: the export happened, but the runner gave up | correct on the first try: "Export selected" became "Download selected" | 10 | 162.9 s |

Attempts count every try, retries included; each plan has 5 steps.

On layout b, both page changes were repaired correctly and the page ended showing "Exported 1 invoice: INV-1042",
but the screenshot checker returned "not ok" twice while its own explanation said the page matched, so the runner
gave up. Two steps on that run also timed out on elements the layout did not change, probably because other
work was using the CPU at the time (not verified). The weak point in this run was the checker, not the repair.
A fix for the checker and a re-test of layout b are in progress.

The fake-mode files in `results/` are pipeline tests and are not model results.

## Limits
- Only localhost pages, and only the demo invoice app has been tested.
- Every step waits for a model call on a laptop CPU: about 20 to 40 s per step when nothing goes wrong, almost
  all of it model time, so a 5-step task takes 2 to 3 minutes.
- The screenshot checker can contradict itself (see layout b above), so a run can give up on a page that is correct.
- The recorder covers standard form controls, not every ARIA pattern.

## Links
- Code: https://github.com/rjw-create/hack-or-treat-shadow
- Demo video: [link after recording]
