# Demo script (3 minutes)

What to click and what to say, timed to the minute.

Each Gemma 4 screenshot check is expected to take tens of seconds on this laptop's CPU, so one 5-step run
takes minutes and two live runs cannot fit in 3 minutes. The plan: record live, show the planning and the two
runs from the backup video sped up, then open the real report live. Say out loud that the video is sped up, and
keep the speed label on screen.

Measured with Gemma 4 on this machine (fill in after the first real run): planning __ s, run layout a __ s,
run layout b __ s, time per step __ s.

## Before going on stage (not part of the 3 minutes)
All commands are PowerShell, run from the project folder.

1. Terminal 1, start the demo site and leave it running:
   ```
   .venv\Scripts\python -m http.server 8000
   ```
2. Terminal 2, set the model tags:
   ```
   $env:SHADOW_PLANNER_MODEL = "<planner tag>"; $env:SHADOW_CHECKER_MODEL = "<checker tag>"
   ```
3. Browser tab 1: the backup video, paused at the start of the planning segment.
4. Browser tab 2: `report.html` of the layout b run shown in the video, scrolled to the top.
5. Close notifications; make the terminal font large enough to read from the back of the room.

## 0:00 to 0:20: the problem
Say: "Browser automations break as soon as a page changes. Shadow learns a task from watching you do it once,
and when the page changes, Gemma 4 running on this laptop repairs the plan. The screenshots never leave the machine."

## 0:20 to 0:50: record the task, live
Do, in terminal 2:
```
.venv\Scripts\python -m shadow.record http://localhost:8000/demo_site/invoices.html
```
In the browser that opens: type "Acme" in Search customer, set Status to Unpaid, tick INV-1042, click Export selected.
Close the browser window to stop recording.

Say while clicking: "It records each action by role and accessible name, like button 'Export selected', not by pixel
position or CSS selector."

## 0:50 to 1:10: the plan (video)
Switch to the video tab and play.

Say: "This is the same recording turned into a plan by Gemma 4, sped up. Each step has an intent, one action from a
fixed list, a target, and what the page should show afterwards. The model writes JSON that we validate, never code."

## 1:10 to 1:30: run on the normal layout (video)
Say: "For every step, Gemma 4 looks at a screenshot and checks the expected state. Layout a is the page as recorded,
so every step passes."

## 1:30 to 2:10: run on the changed layout, with the repair (video)
Say before step 5: "In layout b, the Export button is renamed Download selected and moved below the table.
A recorded script would stop here."
When the repair line appears, say: "The click times out. Gemma 4 reads the page's accessibility tree, explains what
changed, and returns a patched step. Shadow validates it and tries again, and the check passes."

## 2:10 to 2:50: the report, live
Switch to the report tab. Point at the summary row (steps passed, repairs, time per step), then scroll to step 5.

Say: "Every step has its screenshot and the checker's verdict. Here is the repair: the old target is struck out,
the new one is next to it, and the box on the repaired screenshot shows the button it found."

## 2:50 to 3:00: close
Say: "Learned from one demonstration, checked by vision, repaired by Gemma 4, all running on this laptop. The
patched plan is also written out as a plain Playwright script, so you can read what it will do."

## If something goes wrong
| Problem | What to do |
| --- | --- |
| The recorder does not open a browser, or the server is down | Skip to 0:50 and play the video from the start; it includes the recording. |
| The video will not play | Open the report tab and walk through it step by step; it shows the same run. |
| Running short of time | Skip the layout a segment (1:10 to 1:30). |

## Recording the backup video (final hour)
- Needs Jackson's go-ahead for real model runs (shared GPU). One task, layouts a, b and e.
- Record the screen at normal speed, then speed up the waits in the edit and show the speed on screen (for example "8x").
- Keep the terminal and the browser both visible during the runs.
- Afterwards, generate the reports with `python -m viewer.report` for the same runs, so tab 2 matches the video.
- Fill in the "Measured" line at the top from the run's own output.
