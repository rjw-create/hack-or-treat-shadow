# Demo script (3 minutes, live)

What to click and what to say, timed to the minute. Times are targets until we rehearse with the real
models; after the first rehearsal, write the measured plan and run times into the "Measured" lines.

## Before going on stage (not part of the 3 minutes)
All commands are PowerShell, run from the project folder. Use three terminals, already open.

1. Terminal 1, start the demo site and leave it running:
   ```
   .venv\Scripts\python -m http.server 8000
   ```
2. Set the model tags in terminals 2 and 3:
   ```
   $env:SHADOW_PLANNER_MODEL = "<planner tag>"; $env:SHADOW_CHECKER_MODEL = "<checker tag>"
   ```
3. Warm up both models with one throwaway run of a known-good plan, so the first live call does not pay the model load time.
4. Have a finished, good run ready as a safety net: a `runs/<id>/` folder with `plan.json` and an `exec/` folder with its
   `report.html` already generated, open in a browser tab.
5. Have the backup video open in a paused player in another tab.
6. Close notifications; set the terminal font large enough to read from the back of the room.

## 0:00 to 0:30: the problem and the recording
Say: "Browser automations break as soon as a page changes. Shadow learns a task from watching you do it once,
and when the page changes, a local Gemma 4 model repairs the plan. Nothing leaves this laptop."

Do, in terminal 2:
```
.venv\Scripts\python -m shadow.record http://localhost:8000/demo_site/invoices.html
```
In the browser that opens: type "Acme" in Search customer, set Status to Unpaid, tick INV-1042, click Export selected.
Close the browser to stop recording.

Say while clicking: "It records each action by role and accessible name, like button 'Export selected', not by pixel position or CSS selector."

## 0:30 to 1:00: the plan
Do, in terminal 2 (use the run id the recorder printed):
```
.venv\Scripts\python -m shadow.plan runs\<run id>
```
Then open `runs\<run id>\plan.json`.

Say: "Gemma 4 turns the recording and a few screenshots into a plan: each step has an intent, one action from a fixed list,
a target, and what the page should look like afterwards. The model writes JSON that we validate, never code."

Measured planning time: (fill in after rehearsal)

## 1:00 to 1:30: run on the normal layout
Do:
```
.venv\Scripts\python -m shadow.run runs\<run id>\plan.json --layout a
```
Say while it runs: "For every step, a second Gemma 4 call looks at a screenshot and checks the expected state.
The checker sees the page as an image, so it confirms what is on the screen, not only what is in the code."

Measured run time, layout a: (fill in after rehearsal)

## 1:30 to 2:15: run on the changed layout, showing the repair
Do:
```
.venv\Scripts\python -m shadow.run runs\<run id>\plan.json --layout b
```
Say before step 5: "In layout b the Export button is renamed to Download selected and moved below the table.
A recorded script would stop here."
When the repair line prints, point at it and say: "The click times out. The planner reads the page's accessibility tree,
explains what changed, and returns a patched step. The runner validates it and tries again, and the check passes."

Measured run time, layout b: (fill in after rehearsal)

## 2:15 to 2:50: the report
Do, in terminal 3 (use the exec id from the run):
```
.venv\Scripts\python -m viewer.report runs\<run id>\exec\<exec id>
```
Open the `report.html` it prints. Scroll to step 5.

Say: "The report shows each step with its screenshot and check verdict. Here is the repair: the old target is
struck out, the new target is next to it, and the failed and repaired screenshots are side by side."
Point at the summary row: steps passed, repairs, time per step.

## 2:50 to 3:00: close
Say: "Learned from one demonstration, checked by vision and repaired by a local Gemma 4. It also writes out the
patched plan as a plain Playwright script, so you can see what it will do before you run it."

## If something goes wrong
| Problem | What to do |
| --- | --- |
| Planning or a run is still going after 45 s | Say "The model is still thinking, so here is the same run recorded earlier", switch to the backup video tab and play from the matching point. |
| A run fails | Say "This is the case the report is built for" and open the failed run's report.html. If no report was written, switch to the backup video. |
| The browser does not open, or the server is down | Switch to the backup video and narrate over it. |
| `viewer.report` says there is no run.json | Open the pre-made report.html tab from setup step 4. |

## Dependencies on work that is not merged yet
- The runner does not write `run.json` or the `exec/<id>/` folder yet (see `docs/interface.md`). Until it does,
  the 2:15 segment can only use the pre-made fixture report (`viewer/fixtures/repaired_run/report.html`), with placeholder
  screenshots. Check this before rehearsing.
- The backup video does not exist yet; it is recorded in the final hour from a good real run.
