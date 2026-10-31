"""Turn one run log into a static HTML report you can open from disk.

Usage: python -m viewer.report runs/<recording_id>/exec/<exec_id>
Writes report.html next to run.json, so the relative screenshot paths in run.json resolve as they are.
The page has no JavaScript; every value from run.json is escaped, because model-written text is untrusted.
"""
import argparse
import html
import json
import math
import re
import struct
import sys
from pathlib import Path

# Only plain files inside the exec folder's shots/ may become an <img src>; anything else is dropped.
SHOT_PATH = re.compile(r"^shots/[A-Za-z0-9_.-]+\.png$")

STATUS_LABELS = {"passed": "Passed", "repaired": "Repaired", "failed": "Failed", "not_run": "Not run"}
# check.used names the runner argument; the CLI wires check to a text check and visual_check to a screenshot check.
CHECK_LABELS = {"check": "Text check", "visual_check": "Screenshot check"}

CSS = """
:root { --color-bg: #FAFAF7; --color-card: #FFFFFF; --color-text: #1A1A1A; --color-muted: #5E5E5E;
  --color-line: #E2E2DC; --color-accent: #2F6FEB; --color-danger: #C2410C; --color-ok: #1F7A3A;
  --color-warn: #8A5A00; --color-del-bg: #FBE4DA; --color-ins-bg: #DDF2E2; --color-highlight: #C026D3;
  --radius: 12px; }
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
.shot { display: block; position: relative; }
/* Drawn outside the element in a color the demo site doesn't use, so it shows on a blue button too. */
.bbox { position: absolute; outline: 3px solid var(--color-highlight); outline-offset: 3px; border-radius: 4px;
  pointer-events: none; }
.bbox.bad { outline-color: var(--color-danger); }
.shot-note { margin: 4px 0 0; font-size: 14px; }
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


def png_size_px(path):
    """(width, height) in pixels from the PNG header, or None if the file is not a PNG."""
    with open(path, "rb") as f:
        head = f.read(24)
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", head[16:24])


def bbox_style(bbox, size_px):
    """CSS that places bbox over the scaled screenshot, in percent; None if bbox is unusable.
    Assumes 1 CSS px = 1 screenshot px, which holds for the runner's default device scale factor."""
    if not isinstance(bbox, dict) or not size_px or 0 in size_px:
        return None
    vals = [bbox.get(k) for k in ("x", "y", "width", "height")]
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in vals):
        return None
    x, y, w, h = vals
    img_w, img_h = size_px
    left, top = max(0.0, x), max(0.0, y)
    right, bottom = min(float(img_w), x + w), min(float(img_h), y + h)
    if right <= left or bottom <= top:
        return None
    return (f"left:{left / img_w * 100:.3f}%;top:{top / img_h * 100:.3f}%;"
            f"width:{(right - left) / img_w * 100:.3f}%;height:{(bottom - top) / img_h * 100:.3f}%")


def shot_html(exec_dir, path, alt, bbox=None, bad=False):
    if not isinstance(path, str) or not SHOT_PATH.match(path):
        return '<div class="noshot muted">No screenshot</div>'
    if not (exec_dir / path).is_file():
        return f'<div class="noshot muted">Screenshot missing: <code>{esc(path)}</code></div>'
    style = bbox_style(bbox, png_size_px(exec_dir / path))
    box = f'<span class="bbox{" bad" if bad else ""}" style="{style}"></span>' if style else ""
    return f'<a class="shot" href="{esc(path)}"><img src="{esc(path)}" alt="{esc(alt)}" loading="lazy">{box}</a>'


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
        + (f'<p class="muted">No change to the step: <code>{esc(after)}</code></p>' if before == after else
           f'<p><code><del>{esc(before)}</del></code> &rarr; <code><ins>{esc(after)}</ins></code></p>')
        + '</div>'
    )


def attempt_html(exec_dir, step_index, attempt):
    n = attempt.get("attempt", "?")
    step = attempt.get("step") or {}
    check = attempt.get("check")
    if not attempt.get("action_ok"):
        result = f'<span class="bad">Action failed</span>: <code>{esc(attempt.get("error"))}</code>'
    elif check:
        kind = CHECK_LABELS.get(check.get("used"), "Check")
        verdict = '<span class="ok">passed</span>' if check.get("ok") else '<span class="bad">failed</span>'
        result = f'{esc(kind)} {verdict}: {esc(check.get("reason"))}'
    else:
        result = '<span class="muted">No check</span>'
    passed = bool(attempt.get("action_ok") and check and check.get("ok"))
    bbox = attempt.get("bbox")
    target = step.get("target") or {}
    if target and bbox:
        note = f'<p class="shot-note muted">Box: where <code>{esc(describe({**step, "value": None}))}</code> was found</p>'
    elif target and not attempt.get("action_ok"):
        note = '<p class="shot-note muted">Target not found on this page</p>'
    else:
        note = ""
    parts = [
        '<div class="attempt">',
        f'<h3>Attempt {esc(n)}</h3>',
        shot_html(exec_dir, attempt.get("screenshot"), f"Page after step {step_index}, attempt {n}",
                  bbox=bbox, bad=not passed),
        note,
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
    recording = f' of recording {esc(run["recording_id"])}' if run.get("recording_id") else ""
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
  <p class="muted">Run {esc(run.get("exec_id"))}{recording},
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
