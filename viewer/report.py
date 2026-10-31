"""Turn one run log into a static HTML report you can open from disk.

Usage: python -m viewer.report runs/<recording_id>/exec/<exec_id>
Writes report.html next to run.json, so the relative screenshot paths in run.json resolve as they are.
The page has no JavaScript; every value from run.json is escaped, because model-written text is untrusted.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

# Only plain files inside the exec folder's shots/ may become an <img src>; anything else is dropped.
SHOT_PATH = re.compile(r"^shots/[A-Za-z0-9_.-]+\.png$")

STATUS_LABELS = {"passed": "Passed", "repaired": "Repaired", "failed": "Failed", "not_run": "Not run"}

CSS = """
:root { --color-bg: #FAFAF7; --color-card: #FFFFFF; --color-text: #1A1A1A; --color-muted: #5E5E5E;
  --color-line: #E2E2DC; --color-accent: #2F6FEB; --color-danger: #C2410C; --color-ok: #1F7A3A;
  --color-warn: #8A5A00; --color-del-bg: #FBE4DA; --color-ins-bg: #DDF2E2; --radius: 12px; }
@media (prefers-color-scheme: dark) {
  :root { --color-bg: #15161A; --color-card: #1F2026; --color-text: #ECECEA; --color-muted: #A8A8A3;
    --color-line: #34353D; --color-accent: #7FA6FF; --color-danger: #FF8A5C; --color-ok: #6FD08C;
    --color-warn: #F2C46B; --color-del-bg: #4A2618; --color-ins-bg: #1D3B26; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--color-bg); color: var(--color-text);
  font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1100px; margin: 0 auto; padding: 24px 16px 48px; }
h1 { font-size: 24px; margin: 0 0 4px; }
h2 { font-size: 20px; margin: 0; }
.muted { color: var(--color-muted); font-size: 14px; }
.card { background: var(--color-card); border: 1px solid var(--color-line); border-radius: var(--radius);
  padding: 16px; margin-top: 16px; }
.summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-top: 16px; }
.stat { background: var(--color-card); border: 1px solid var(--color-line); border-radius: var(--radius); padding: 12px; }
.stat b { display: block; font-size: 24px; }
.verdict { font-size: 20px; font-weight: 700; margin-top: 12px; }
.ok { color: var(--color-ok); } .bad { color: var(--color-danger); } .warn { color: var(--color-warn); }
.step-head { display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: baseline; }
.badge { font-size: 14px; font-weight: 600; padding: 2px 10px; border-radius: 999px; border: 1px solid currentColor; }
dl { display: grid; grid-template-columns: max-content 1fr; gap: 4px 12px; margin: 12px 0 0; }
dt { color: var(--color-muted); font-size: 14px; }
dd { margin: 0; overflow-wrap: anywhere; }
code { font-family: ui-monospace, Consolas, monospace; font-size: 14px; }
.attempts { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 300px), 480px)); gap: 12px;
  margin-top: 12px; }
.attempt { border: 1px solid var(--color-line); border-radius: var(--radius); padding: 12px; min-width: 0; }
.attempt h3 { font-size: 16px; margin: 0 0 8px; }
.shot img { display: block; width: 100%; height: auto; border: 1px solid var(--color-line); border-radius: 8px; }
.noshot { padding: 24px 8px; text-align: center; border: 1px dashed var(--color-line); border-radius: 8px; }
.repair { margin-top: 12px; padding: 12px; border-left: 4px solid var(--color-accent); background: var(--color-bg);
  border-radius: 0 8px 8px 0; }
.repair p { margin: 0 0 8px; }
del { background: var(--color-del-bg); text-decoration: line-through; padding: 0 4px; border-radius: 4px; }
ins { background: var(--color-ins-bg); text-decoration: none; padding: 0 4px; border-radius: 4px; font-weight: 600; }
a { color: var(--color-accent); }
a:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
"""


def esc(value):
    return html.escape("" if value is None else str(value), quote=True)


def seconds(value):
    try:
        return f"{float(value):.1f} s"
    except (TypeError, ValueError):
        return "-"


def describe(step):
    """One-line, unescaped description of what a step does, e.g. click button "Export selected"."""
    if not isinstance(step, dict):
        return ""
    action = step.get("action", "?")
    target = step.get("target") or {}
    parts = [str(action)]
    if target:
        parts.append(f'{target.get("role", "?")} "{target.get("name", "")}"')
    if step.get("value") is not None:
        parts.append(f'= "{step["value"]}"' if target else str(step["value"]))
    return " ".join(parts)


def shot_html(exec_dir, path, alt):
    if not isinstance(path, str) or not SHOT_PATH.match(path):
        return '<div class="noshot muted">No screenshot</div>'
    if not (exec_dir / path).is_file():
        return f'<div class="noshot muted">Screenshot missing: <code>{esc(path)}</code></div>'
    return f'<a class="shot" href="{esc(path)}"><img src="{esc(path)}" alt="{esc(alt)}" loading="lazy"></a>'


def repair_html(repair, before_step):
    after_step = repair.get("new_step") or {}
    before, after = describe(before_step), describe(after_step)
    accepted = repair.get("accepted")
    verdict = ('<span class="ok">accepted</span>' if accepted
               else '<span class="bad">rejected (failed validation)</span>')
    return (
        '<div class="repair">'
        f'<p><strong>Repair</strong> by the planner, {verdict}, {esc(seconds(repair.get("repair_s")))}</p>'
        f'<p>{esc(repair.get("explanation"))}</p>'
        f'<p><code><del>{esc(before)}</del></code> &rarr; <code><ins>{esc(after)}</ins></code></p>'
        '</div>'
    )


def attempt_html(exec_dir, step_index, attempt):
    n = attempt.get("attempt", "?")
    step = attempt.get("step") or {}
    check = attempt.get("check")
    if not attempt.get("action_ok"):
        result = f'<span class="bad">Action failed</span>: <code>{esc(attempt.get("error"))}</code>'
    elif check and check.get("ok"):
        result = f'<span class="ok">Check passed</span>: {esc(check.get("reason"))}'
    elif check:
        result = f'<span class="bad">Check failed</span>: {esc(check.get("reason"))}'
    else:
        result = '<span class="muted">No check</span>'
    parts = [
        '<div class="attempt">',
        f'<h3>Attempt {esc(n)}</h3>',
        shot_html(exec_dir, attempt.get("screenshot"), f"Page after step {step_index}, attempt {n}"),
        f'<dl><dt>Did</dt><dd><code>{esc(describe(step))}</code></dd>',
        f'<dt>Result</dt><dd>{result}</dd>',
        f'<dt>Time</dt><dd>action {esc(seconds(attempt.get("action_s")))}, '
        f'check {esc(seconds(attempt.get("check_s")))}</dd></dl>',
    ]
    if attempt.get("repair"):
        parts.append(repair_html(attempt["repair"], step))
    parts.append('</div>')
    return "".join(parts)


def step_html(exec_dir, step):
    status = step.get("status", "not_run")
    cls = {"passed": "ok", "repaired": "warn", "failed": "bad"}.get(status, "muted")
    planned = step.get("planned") or {}
    attempts = step.get("attempts") or []
    body = "".join(attempt_html(exec_dir, step.get("index"), a) for a in attempts)
    return (
        f'<section class="card" aria-labelledby="step-{esc(step.get("index"))}">'
        '<div class="step-head">'
        f'<h2 id="step-{esc(step.get("index"))}">Step {esc(step.get("index"))}: {esc(planned.get("intent"))}</h2>'
        f'<span class="badge {cls}">{esc(STATUS_LABELS.get(status, status))}</span>'
        f'<span class="muted">{esc(seconds(step.get("time_s")))}</span>'
        '</div>'
        f'<dl><dt>Planned</dt><dd><code>{esc(describe(planned))}</code></dd>'
        f'<dt>Expected</dt><dd>{esc(planned.get("expected"))}</dd></dl>'
        + (f'<div class="attempts">{body}</div>' if attempts else '<p class="muted">This step was not reached.</p>')
        + '</section>'
    )


def render(run, exec_dir):
    summary = run.get("summary") or {}
    models = run.get("models") or {}
    if run.get("ok"):
        verdict = '<p class="verdict ok">Run passed</p>'
    else:
        verdict = f'<p class="verdict bad">Run failed at step {esc(run.get("failed_step"))}</p>'
    stats = [
        ("Steps passed", f'{summary.get("steps_passed", "-")} / {summary.get("steps_total", "-")}'),
        ("Repairs", f'{summary.get("repairs_succeeded", "-")} of {summary.get("repairs_attempted", "-")} worked'),
        ("Time per step", seconds(summary.get("time_per_step_s"))),
        ("Total time", seconds(run.get("duration_s"))),
    ]
    stat_html = "".join(f'<div class="stat"><span class="muted">{esc(k)}</span><b>{esc(v)}</b></div>' for k, v in stats)
    steps = "".join(step_html(exec_dir, s) for s in run.get("steps") or [])
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Shadow run {esc(run.get("exec_id"))}</title>
<style>{CSS}</style>
</head>
<body>
<main>
  <h1>{esc(run.get("task"))}</h1>
  <p class="muted">Run {esc(run.get("exec_id"))} of recording {esc(run.get("recording_id") or "none")},
    layout {esc(run.get("layout") or "default")}, started {esc(run.get("started_at"))}.
    Planner <code>{esc(models.get("planner"))}</code>, checker <code>{esc(models.get("checker"))}</code>.</p>
  {verdict}
  <div class="summary">{stat_html}</div>
  {steps}
</main>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description="Write report.html for one Shadow run.")
    parser.add_argument("exec_dir", type=Path, help="runs/<recording_id>/exec/<exec_id>")
    args = parser.parse_args()
    run_path = args.exec_dir / "run.json"
    try:
        run = json.loads(run_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"No run.json in {args.exec_dir}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"{run_path} is not valid JSON: {e}", file=sys.stderr)
        return 1
    if run.get("schema_version") != 1:
        print(f"Warning: schema_version {run.get('schema_version')!r}, this viewer expects 1", file=sys.stderr)
    out = args.exec_dir / "report.html"
    out.write_text(render(run, args.exec_dir), encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
