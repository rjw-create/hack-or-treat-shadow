# Real Gemma 4 runs on the new page-change layouts (2026-11-03)

Task `export_invoice` on layouts f, g and h, 3 runs each (9 runs). The other two suite tasks have not been run on
these layouts.

Raw files, each line holding the full run.json:
- `2026-11-03-194836-gemma-runs.jsonl`: layouts f and g (6 runs, code `922d4cf`). This eval was started for all
  three tasks on f, g and h (27 runs), but it was stopped at 20:00 after 12 minutes, because Claude Code stops
  background commands when the machine runs low on memory. The runner writes one line per finished run, so these 6
  runs are complete. That eval never reached its end, so it has no `-summary.json`.
- `2026-11-03-205918-gemma-runs.jsonl` and `-summary.json`: layout h (3 runs, code `5df03e6`, which differs from
  `922d4cf` only in `results/`).

Neither run had uncommitted changes in `shadow/` or `evals/`. Setup: `gemma4:e4b` as planner and checker through
Ollama on the same laptop as the 2026-10-31 runs. Headless browser, model loaded before timing started.

## The new layouts
| Layout | Page change | Step it breaks |
| --- | --- | --- |
| f | Only the search label renamed, to "Filter by company" | fill searchbox "Search customer" |
| g | Export button moved next to the page title and shortened to "Export" | click button "Export selected" |
| h | Status dropdown replaced by radios "All", "Settled", "Outstanding" | select combobox "Status" |

A button that only moves keeps its role and name, and the runner finds elements by exact role and name, so a
move alone breaks no step. That is why g also shortens the name.

## Results (task `export_invoice`, 3 runs per layout)
| Layout | Task success | Repairs (succeeded / attempted) | Mean `time_s` of the repaired step | Mean `repair_s` (model call only) | Mean time per step |
| --- | --- | --- | --- | --- | --- |
| f | 3 / 3 | 3 / 3 | 67.0 s (95.5, 53.6, 51.9) | 41.5 s | 24.1 s |
| g | 3 / 3 | 3 / 3 | 57.8 s (81.9, 45.2, 46.3) | 34.9 s | 22.8 s |
| h | 3 / 3 | 3 / 3 | 77.3 s (121.4, 54.9, 55.6) | 51.7 s | 25.9 s |
| all | 9 / 9 | 9 / 9 | 67.4 s | 42.7 s | 24.3 s |

- Every repair worked on the first try. Each repaired step took 2 attempts, and each retry passed the screenshot
  check.
  - f: `Search customer` became `Filter by company`.
  - g: `Export selected` became `Export`.
  - h: Gemma 4 changed the action from `select` on the Status combobox to `click` on the `Outstanding` radio,
    so it matched "Unpaid" to a different word as well as switching control type.
- A repaired step's `time_s` covers the failed attempt (it waits the full 10 s action timeout), the repair call,
  the retried action and its screenshot check.
- The first run of each layout was much slower than runs 2 and 3 (task 200.4 s, 192.3 s and 227.4 s, against
  73.6 to 82.5 s). The raw files don't show why.
- Task success means the runner reported success and the page showed `Exported 1 invoice: INV-1042`.

## How the numbers were checked
Recomputed from the raw JSONL with a separate script: repairs counted from each step's attempts (a repair succeeded
if the next attempt's action ran and its check said ok), compared against the `repairs_succeeded` and
`repairs_attempted` fields in each line (they match: 9 / 9), and `time_s` read from each repaired step. For layout h,
the runner's own `-summary.json` agrees (3 / 3 repairs, 25.944 s per step).
