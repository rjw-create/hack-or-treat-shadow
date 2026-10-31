# Demo script (3 minutes)

What to click and what to say, timed to the minute.

Gemma 4 calls take tens of seconds each on this laptop's CPU, so one 5-step run takes about 3 minutes and two
live runs cannot fit in 3 minutes. The plan: record live, show the planning and the two runs from the backup
video sped up, then open the real report live. Say out loud that the video is sped up, and keep the speed label
on screen.

Measured in the runs shown in the backup video (gemma4:e4b on CPU, one run per layout, after Core's checker and
timeout fixes; source `results/2026-10-31-gemma-run-notes.md`): layout a 121 s, layout b 156 s (33.4 s repair),
layout e 175 s (53.4 s repair); 30.2 s per step on average. All 3 tasks passed; both repairs worked on the first try.

The backup video is `runsideo\shadow-backup.mp4` in this worktree (77 s): a title card, then layouts a, b
and e (each with a card naming the page change and the repair), then a still of the layout e report. Every
sped-up clip is labelled with its real speed. It does not show recording or planning: these eval runs start from
a hand-written plan (`evals/tasks/export_invoice.json`), so never say the video's plan was made by Gemma 4.

## Before going on stage (not part of the 3 minutes)
All commands are PowerShell, run from the project folder.

1. Terminal 1, start the demo site and leave it running:
   ```
   .venv\Scripts\python -m http.server 8000
   ```
2. Terminal 2, set the model tags:
   ```
   $env:SHADOW_PLANNER_MODEL = "gemma4:e4b"; $env:SHADOW_CHECKER_MODEL = "gemma4:e4b"
   ```
3. Browser tab 1: the backup video (`runsideo\shadow-backup.mp4`), paused at the start.
4. Browser tab 2: the layout e `report.html` from the same runs (`runsetest\<layout e folder>eport.html`),
   scrolled to the top. Tab 3: the layout b report from the same runs.
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

## 0:50 to 1:00: what a plan looks like
Open `evals/tasks/export_invoice.json` (the plan the video's runs use) in an editor.

Say: "From a recording like that, Gemma 4 writes a plan like this one. Each step has an intent, one action from a
fixed list, a target, and what the page should show afterwards. The model writes JSON that we validate, never code.
The runs you are about to see use this plan on three versions of the page."

## 1:00 to 2:17: the runs (video, 77 s)
Switch to tab 1 and play. Say once at the start: "Gemma 4 runs on this laptop's CPU, so the waits are sped up;
the label on each clip shows how much."
- Layout a card: "First the page as recorded. After every step Gemma 4 checks the expected state: routine steps
  from the page's text, the last step from a screenshot."
- Layout b card: "Now the Export button is renamed Download selected and moved. A recorded script would stop at
  step 5. Gemma 4 reads the page's accessibility tree, finds the renamed button, and the screenshot check confirms
  the export."
- Layout e card: "Here the Status dropdown has become radio buttons. Gemma 4 changes the action itself, from select
  to click on Unpaid, not just a name."
- Report still: "And every run leaves a report."

## 2:17 to 2:50: the report, live
Switch to tab 2 (layout e). Point at the summary row (steps passed, repairs, time per step), then scroll to step 3.

Say: "Every step has its screenshot and the checker's verdict, labelled text or screenshot check. Here is the
repair in Gemma's own words: the old step is struck out, the new one is next to it, and the box on the repaired
screenshot shows the radio button it found."

If a judge asks about failures: "In our first real run, the checker rejected a correct page on layout b and the
runner gave up, even though the repair was right. Core fixed the checker; in the re-test you just saw, all three
layouts passed. That's one run per layout, so it's not a success rate yet."

## 2:50 to 3:00: close
Say: "Learned from one demonstration, checked and repaired by Gemma 4, all running on this laptop. The
patched plan is also written out as a plain Playwright script, so you can read what it will do."

## If something goes wrong
| Problem | What to do |
| --- | --- |
| The recorder does not open a browser, or the server is down | Say what the recorder does, then skip to 0:50. |
| The video will not play | Open the report tab and walk through it step by step; it shows the same run. |
| Running short of time | Skip the plan file (0:50 to 1:00) and cut the report to the summary row. |

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
