# First real Gemma 4 eval run (2026-10-31, 13:37-13:56)

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
