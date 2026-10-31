# Real Gemma 4 eval runs (2026-10-31)

Two real runs, one run per layout each: the first run (13:37-13:56), and a re-test (14:08-14:16) after Shadow
Core's checker and timeout fixes (PRs #16 and #17). **The re-test is the one to quote**; the first run shows what
those fixes changed.

## Re-test after Core PRs #16 and #17 (14:08-14:16)

Raw: `2026-10-31-140849-gemma-runs.jsonl` (layout b, run first) and `2026-10-31-141134-gemma-runs.jsonl`
(layouts a and e), with matching `-summary.json` files. Both record code commit `a23682c` with no uncommitted
changes, which includes #16 (one structured check verdict, text-check second opinion, 10 s action timeout) and #17
(the check prompt says the step has already happened). Same setup as the first run: `gemma4:e4b` as planner
and checker on CPU, task `export_invoice`, headed browser with page video (`--show --video`). The model was
loaded before timing started, and the coordinator declared a quiet period on the machine for this window.

| Layout | Page change | Task success | Runner ok | Page end state correct | Repairs (succeeded / attempted) | Mean time per step |
| --- | --- | --- | --- | --- | --- | --- |
| a | none | yes | yes | yes | 0 / 0 | 24.2 s |
| b | export button renamed and moved | yes | yes | yes | 1 / 1 | 31.1 s |
| e | status dropdown became radio buttons | yes | yes | yes | 1 / 1 | 35.1 s |

- **3 of 3 tasks succeeded, and 2 of 2 repairs succeeded, each on the first try.**
  - b: renamed `Export selected` to `Download selected` (33.4 s).
  - e: changed `select` on the Status combobox to `click` on the `Unpaid` radio button (53.4 s).
- **The checker agreed with the page every time.** No `ok: false` on a correct page, and the runner's verdict matched the
  page check in all 3 runs. In the first run, the screenshot checker turned down the correct layout-b page twice.
- **No timeouts on unchanged elements.** The only failed actions were the two the layouts were built to break.
  Each waited the full 10 s timeout before its repair.
- **Time:** 30.2 s per step over all 15 steps (15-29 s per model check; actions that found their element took under 3 s); a whole
  5-step task took 2.0-2.9 min. Layout a's first check (25.2 s) is in line with the others, so the model
  warm-up removed the cold-start effect seen in the first run.
- **Layout b compared with the first run:** 155.6 s instead of 814.7 s, 6 attempts instead of 10, and the runner
  finished instead of giving up.
- **Still 1 run per layout.** This shows the fixed pipeline working end to end on all three layouts. It is not
  a success rate.

Run folders (git-ignored, on Jackson's machine) each hold `run.json`, `shots/` and `video.webm`:
`runs/eval-2026-10-31-140849/exec/2026-10-31_140851-export_invoice-b-1`,
`runs/eval-2026-10-31-141134/exec/2026-10-31_141136-export_invoice-a-1`,
`runs/eval-2026-10-31-141134/exec/2026-10-31_141338-export_invoice-e-1`.

---

# First run (13:37-13:56)

Raw: `2026-10-31-133731-gemma-runs.jsonl` (full run.json per run). Summary: `2026-10-31-133731-gemma-summary.json`.
Setup: `gemma4:e4b` as planner and checker, through Ollama on CPU (Intel Arc 140V laptop, 32 GB shared RAM), one run
per layout, task `export_invoice`, text check on most steps, screenshot check on the last step and after repairs.
Sample size is 3 runs, so treat every rate here as an anecdote, not a measurement.

| Layout | Page change | Task success | Runner ok | Page end state correct | Repairs (succeeded / attempted) | Mean time per step |
| --- | --- | --- | --- | --- | --- | --- |
| a | none | yes | yes | yes | 0 / 0 | 24.7 s |
| b | export button renamed and moved | no | no (gave up at step 5) | **yes** | 2 / 5 | 162.9 s |
| e | status dropdown became radio buttons | yes | yes | yes | 1 / 1 | 32.6 s |

## What the layout changes tested
- **Layout e:** E4B read the accessibility tree and changed the step's action, from `select` on the Status
  combobox to `click` on the `Unpaid` radio button. The task then finished. 45.6 s for the repair.
- **Layout b, step 5:** E4B renamed the target from `Export selected` to `Download selected` on its first
  try (45.7 s), and the click worked.

So both page changes the layouts introduce were repaired correctly on the first repair.

## Why layout b still failed
1. **Timeouts on elements layout b did not change.** Step 2 (search box) and step 4 (row checkbox) are the
   same in layouts a and b, but their actions hit the runner's 3 s timeout. Repair calls during this time were also slow
   (213 s and 136 s, against about 45 s elsewhere), which points to CPU contention. Shadow Core confirmed it ran
   `check.sh` about 4 times (each starts headless browsers for 40 to 120 s), plus a fresh-clone setup and fake evals,
   between about 13:40 and 13:56, overlapping this run. So contention is likely, but it is not proven to have
   caused these timeouts. On step 2, E4B's first
   repair changed the role to `input` (not a valid ARIA role), and its second changed it back to `searchbox`.
   On step 4 it resubmitted the same step, which then worked.
2. **The screenshot checker turned down a correct page twice.** After the correct repair, the page showed
   "Exported 1 invoice: INV-1042". On attempt 2 the checker returned `ok: false` because it expected to see the
   click itself in the screenshot. On attempt 3 it returned `ok: false` while its own reason said the page
   matched. The runner gave up. The eval's own page check (`end_state_ok`) confirms the task
   was in fact done. This is why task success needs the page check: the runner's verdict alone was wrong here.

## Takeaways
- Repair (planner) worked on both real page changes. The weak point in this run was the checker, which turned down
  a correct page twice (Core PR #16 targets both causes).
- The 2 / 5 repair rate on layout b mixes in failures the layout did not cause: timeouts under load and checker
  errors. Separate them before quoting it.
- Time per step on CPU is about 20-40 s when nothing goes wrong, almost all of it model time
  (actions take under 1 s).

## How to read the numbers
- **Headline metric: task success**, meaning the runner said ok **and** the page shows the expected end state.
  `runner_ok_rate` is the runner's own verdict and is wrong whenever the checker is wrong.
- **`steps_per_task` in the summary JSON counts attempts**, retries included, not plan steps. All three plans have 5 steps;
  layout b used 10 attempts. Later summaries name this `attempts_per_task`.
- **Don't quote the overall 73.4 s per step as typical.** Layout b's slow repairs dominate it. "About 20-40 s per
  step when nothing goes wrong" is the fair summary.
- **`time_per_step_s` in the summary is the mean over every step that ran, pooled across runs.** `run.json`'s own
  `summary.time_per_step_s` is per run.
- **Model cold start:** the model was not loaded beforehand, so layout a's first check (37.7 s) probably includes
  loading it. Step 1's check took 30.2 s on b and 25.9 s on e. Without layout a's step 1, layout a's mean time per step
  is 21.4 s instead of 24.7 s. Later gemma-mode runs warm the model up before timing.
