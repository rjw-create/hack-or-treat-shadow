# Demo script (3 minutes)

What to click and what to say, timed to the minute.

Gemma 4 calls take tens of seconds each on this laptop's CPU, so one 5-step run takes about 3 minutes and two
live runs cannot fit in 3 minutes. The plan: record live, show the planning and the two runs from the backup
video sped up, then open the real report live. Say out loud that the video is sped up, and keep the speed label
on screen.

Timings from one real run with a repair, reported by Core on 2026-10-31 (one data point, not an eval result):
routine text checks 20 to 30 s, the repair 53.7 s, the final screenshot check 29.5 s, 181 s for all 5 steps.
Replace with the backup video run's own numbers once it is recorded: planning __ s, run layout a __ s,
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
Say: "After every step, Gemma 4 checks the expected state: routine steps from the page's text, and the last step
from a screenshot, the way a person would look. Layout a is the page as recorded, so every step passes."

## 1:30 to 2:10: run on the changed layout, with the repair (video)
Say before step 5: "In layout b, the Export button is renamed Download selected and moved below the table.
A recorded script would stop here."
When the repair line appears, say: "The click times out. Gemma 4 reads the page's accessibility tree, explains what
changed, and returns a patched step. Shadow validates it and tries again, and this time a screenshot check
confirms it worked."

## 2:10 to 2:50: the report, live
Switch to the report tab. Point at the summary row (steps passed, repairs, time per step), then scroll to step 5.

Say: "Every step has its screenshot and the checker's verdict, labelled text or screenshot check. Here is the repair: the old target is struck out,
the new one is next to it, and the box on the repaired screenshot shows the button it found."

## 2:50 to 3:00: close
Say: "Learned from one demonstration, checked and repaired by Gemma 4, all running on this laptop. The
patched plan is also written out as a plain Playwright script, so you can read what it will do."

## If something goes wrong
| Problem | What to do |
| --- | --- |
| The recorder does not open a browser, or the server is down | Skip to 0:50 and play the video from the start; it includes the recording. |
| The video will not play | Open the report tab and walk through it step by step; it shows the same run. |
| Running short of time | Skip the layout a segment (1:10 to 1:30). |

## Recording the backup video (final hour)
Needs Jackson's go-ahead for real model runs (shared GPU). One task, layouts a, b and e, run through Proof's eval
runner with its `--show` flag, so the same run gives the video, the reports and the first real results.

### Tools (built into Windows 11, nothing to install)
- Record: Snipping Tool's screen recording (Win+Shift+R, drag over the whole screen, then Start). Game Bar
  (Win+Alt+R) records only one app window, so it would miss either the terminal or the browser.
- Edit: Clipchamp, to cut the long waits or speed them up, and to add a text label with the speed (for example "8x").

### Window layout (1920 x 1080 screen, or whatever the projector uses)
- Left half: the terminal, font size 16 or larger, so the step log and repair lines are readable in the video.
- Right half: the browser window Playwright opens. It appears when the run starts; drag it to the right half then.
- Hide the taskbar clock and notifications (Focus on); close anything showing names, email or chat.

### Steps
1. Terminal 1: `.venv\Scripts\python -m http.server 8000` if the eval runner needs it (check Proof's `--show` notes).
2. Terminal 2: set `SHADOW_PLANNER_MODEL` and `SHADOW_CHECKER_MODEL`, then warm up each model so the first recorded
   check does not include load time (Ollama unloads an idle model after 5 minutes by default, so start recording soon after):
   ```
   ollama run <checker tag> "Reply OK"
   ```
   ```
   ollama run <planner tag> "Reply OK"
   ```
3. Start the Snipping Tool recording, then start the eval run with `--show` for one task and layouts a, b and e.
4. Stop the recording when the run prints its summary.
5. For each exec folder the run printed, make the report (PowerShell, one folder per command):
   ```
   .venv\Scripts\python -m viewer.report <exec folder>
   ```
   Open the layout b `report.html` in a browser tab; that is tab 2 for the demo.
6. Copy the time per step and run times from the run's printed output into the "Measured" line at the top of this file.
7. In Clipchamp: keep the record segment and the step-5 repair of layout b at normal speed, speed up or cut the
   rest, and keep a visible speed label on every sped-up part. Export at 1080p.
8. Save the video outside the repo and do not commit it; put its link in `2026-10-31-submission.md`.
