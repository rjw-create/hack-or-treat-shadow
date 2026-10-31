# Demo script (3 minutes)

What to click and what to say, timed to the minute.

Gemma 4 calls take tens of seconds each on this laptop's CPU, so one 5-step run takes about 3 minutes and two
live runs cannot fit in 3 minutes. The plan: record live, show the planning and the two runs from the backup
video sped up, then open the real report live. Say out loud that the video is sped up, and keep the speed label
on screen.

Measured in the backup video's run (gemma4:e4b on CPU, one run each; source `results/2026-10-31-gemma-run-notes.md`):
layout a 123 s (24.7 s per step), layout e 163 s (32.6 s per step, including a 45.6 s repair).
Layout b's run gave up at step 5 even though the repair was right and the page was correct: the screenshot
checker said "not ok" while its own reason said the page matched. So the demo shows the layout e repair, not b.

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
4. Browser tab 2: `report.html` of the layout e run shown in the video, scrolled to the top. Tab 3: the layout b
   report, in case a judge asks about failures.
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
Say: "After every step, Gemma 4 checks the expected state: routine steps from the page's text, and the last step
from a screenshot, the way a person would look. Layout a is the page as recorded, so every step passes."

## 1:30 to 2:10: run on the changed layout, with the repair (video, layout e)
Say before step 3: "In this version of the page, the Status dropdown has become radio buttons. The recorded step
selects from a dropdown that no longer exists, so a recorded script would stop here."
When the repair line appears, say: "The select times out. Gemma 4 reads the page's accessibility tree and explains
that the filter is now radio buttons. It changes the action itself, from select to click on Unpaid, not just a
name. Shadow validates the new step and tries again, and a screenshot check confirms the table only shows unpaid
invoices."

## 2:10 to 2:50: the report, live
Switch to the report tab (layout e). Point at the summary row (steps passed, repairs, time per step), then scroll
to step 3.

Say: "Every step has its screenshot and the checker's verdict, labelled text or screenshot check. Here is the
repair in Gemma's own words: the old step is struck out, the new one is next to it, and the box on the repaired
screenshot shows the radio button it found."

If a judge asks about failures: open the layout b report at step 5. The repair to "Download selected" was right
and the page shows the export, but the checker said "not ok" while its own reason said it matched. Say so plainly;
it is the next thing to fix.

## 2:50 to 3:00: close
Say: "Learned from one demonstration, checked and repaired by Gemma 4, all running on this laptop. The
patched plan is also written out as a plain Playwright script, so you can read what it will do."

## If something goes wrong
| Problem | What to do |
| --- | --- |
| The recorder does not open a browser, or the server is down | Skip to 0:50 and play the video from the start; it includes the recording. |
| The video will not play | Open the report tab and walk through it step by step; it shows the same run. |
| Running short of time | Skip the layout a segment (1:10 to 1:30). |

## Making the backup video (automatic, no screen recording)
The browser part is recorded by Playwright during the run (Proof's `--video` flag, one `.webm` per run in each
exec folder). The video is then cut together with ffmpeg in this worktree. No one has to start a screen recorder.

### Rules while the real run is going
From Proof's start message until it reports done: no browser checks, `check.sh`, ffmpeg encoding or other
CPU-heavy work in any other session. CPU contention caused the timeouts in the first layout b run.

### Steps (after Proof reports done)
1. Copy each run's exec folder (run.json, shots/, the .webm) from Proof's worktree into this worktree's git-ignored
   `runs/real/`. Only read Proof's worktree; never write there.
2. Make a report per run: `.venv\Scripts\python -m viewer.report runs\real\<exec folder>`.
3. Build the video with ffmpeg in a git-ignored folder (`runs/video/`), keeping it under about 2 minutes:
   - A title card per segment, taken from the run report: layout, step, check type (text or screenshot), and
     the repair's before and after step.
   - Long model waits sped up with `setpts`, each with an on-screen label such as "model checking, 4x speed".
     The repair moment itself stays at normal speed.
   - Order: layout a (short, sped up), then the repair run (layout e, or b if the re-test passes), then a still of
     the report's repaired step with the target box.
4. Do not commit the video. Put its local path in `2026-10-31-submission.md` for Jackson to upload, and use it
   in the demo's browser tab 1.
5. Fill in the "Measured" line at the top of this file from the run's run.json files.

### Needs
- A full ffmpeg build with `setpts`, `drawtext` and `concat`. Not installed yet: Playwright's bundled ffmpeg only
  has what screencasts need (no `setpts`, `drawtext` or `concat`). Installing one needs Jackson's OK.
