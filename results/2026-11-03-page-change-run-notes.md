# Real Gemma 4 runs on the new page-change layouts (2026-11-03)

**Partial run: 6 of the planned 27 runs finished.** The eval (`--mode gemma --layouts f g h --runs 3`, all three
tasks) was stopped at 20:00 after 12 minutes, because Claude Code stops background commands when the machine runs
low on memory. Only task `export_invoice` on layouts f and g finished. Layout h and the other two tasks did not
run. The runner writes one line per finished run, so the raw file holds those 6 runs complete. Because the run
never reached its end, there is no `-summary.json`.

Raw: `2026-11-03-194836-gemma-runs.jsonl` (6 lines, each with the full run.json). Every line records code commit
`922d4cf` with no uncommitted changes in `shadow/` or `evals/`. Setup: `gemma4:e4b` as planner and checker through
Ollama on the same laptop as the 2026-10-31 runs. Headless browser, model loaded before timing started.

## The new layouts
| Layout | Page change | Step it breaks |
| --- | --- | --- |
| f | Only the search label renamed, to "Filter by company" | fill searchbox "Search customer" |
| g | Export button moved next to the page title and shortened to "Export" | click button "Export selected" |
| h | Status dropdown replaced by radios "All", "Settled", "Outstanding" (not run yet) | select combobox "Status" |

A button that only moves keeps its role and name, and the runner finds elements by exact role and name, so a
move alone breaks no step. That is why g also shortens the name.

## Results (task `export_invoice`, 3 runs per layout)
| Layout | Task success | Repairs (succeeded / attempted) | Mean `time_s` of the repaired step | Mean `repair_s` (model call only) | Mean time per step |
| --- | --- | --- | --- | --- | --- |
| f | 3 / 3 | 3 / 3 | 67.0 s (95.5, 53.6, 51.9) | 41.5 s | 24.1 s |
| g | 3 / 3 | 3 / 3 | 57.8 s (81.9, 45.2, 46.3) | 34.9 s | 22.8 s |
| both | 6 / 6 | 6 / 6 | 62.4 s | 38.2 s | 23.4 s |

- Every repair worked on the first try. Each repaired step took 2 attempts, and each retry passed the screenshot
  check. f: `Search customer` became `Filter by company`. g: `Export selected` became `Export`.
- A repaired step's `time_s` covers the failed attempt (it waits the full 10 s action timeout), the repair call,
  the retried action and its screenshot check.
- The first run of each layout was much slower than runs 2 and 3 (task 200.4 s and 192.3 s, against 73.6 to
  82.5 s). The raw file doesn't show why. Other work on the machine is the likeliest cause, since memory ran out
  soon after.
- Task success means the runner reported success and the page showed `Exported 1 invoice: INV-1042`.

## How the numbers were checked
Recomputed from the raw JSONL with a separate script: repairs counted from each step's attempts (a repair succeeded
if the next attempt's action ran and its check said ok), compared against the `repairs_succeeded` and
`repairs_attempted` fields in each line (they match: 6 / 6), and `time_s` read from each repaired step.
