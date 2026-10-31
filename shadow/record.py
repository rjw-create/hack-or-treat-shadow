"""Record one demonstration in a real browser window.

Usage: python -m shadow.record http://localhost:8000/demo_site/invoices.html
Do the task in the window that opens, then close the window.
Writes runs/<timestamp>/events.jsonl and runs/<timestamp>/shots/NNN.png.
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from shadow.steps import is_allowed_url

# Runs inside every page. It reports semantic targets (role + accessible name), not
# pixel positions, so the plan survives layout changes. The role/name logic is a
# simple approximation that covers standard form controls, not full ARIA rules.
LISTENER_JS = r"""
(() => {
  const roleOf = (el) => {
    if (el.getAttribute("role")) return el.getAttribute("role");
    const tag = el.tagName.toLowerCase();
    if (tag === "button") return "button";
    if (tag === "a" && el.hasAttribute("href")) return "link";
    if (tag === "select") return "combobox";
    if (tag === "textarea") return "textbox";
    if (tag === "input") {
      const t = (el.type || "text").toLowerCase();
      if (t === "checkbox" || t === "radio") return t;
      if (t === "search") return "searchbox";
      if (t === "submit" || t === "button") return "button";
      return "textbox";
    }
    return tag;
  };
  const nameOf = (el) => {
    if (el.getAttribute("aria-label")) return el.getAttribute("aria-label").trim();
    if (el.id) {
      const lab = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (lab) return lab.textContent.trim();
    }
    if (el.closest("label")) return el.closest("label").textContent.trim();
    return (el.textContent || el.value || el.placeholder || "").trim().slice(0, 80);
  };
  const interactive = "button, a[href], input, select, textarea, [role]";
  const send = (type, el, value) => window.__shadowEvent({
    type, role: roleOf(el), name: nameOf(el), value: value ?? null, url: location.href,
  });
  document.addEventListener("click", (e) => {
    const el = e.target.closest(interactive);
    // Clicks that only focus a text field or open a select are noise; their change events matter.
    if (!el || ["textbox", "searchbox", "combobox"].includes(roleOf(el))) return;
    send("click", el);
  }, true);
  document.addEventListener("change", (e) => {
    const el = e.target;
    const role = roleOf(el);
    if (role === "combobox") send("select", el, el.selectedOptions[0]?.textContent.trim() ?? el.value);
    else if (role === "textbox" || role === "searchbox") send("fill", el, el.value);
  }, true);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && ["textbox", "searchbox"].includes(roleOf(e.target))) {
      send("fill", e.target, e.target.value);
      send("press", e.target, "Enter");
    }
  }, true);
})();
"""


def record(start_url, runs_dir=Path("runs")):
    if not is_allowed_url(start_url):
        raise SystemExit(f"Refusing to record outside localhost: {start_url}")
    run_dir = runs_dir / time.strftime("%Y-%m-%d_%H%M%S")
    shots_dir = run_dir / "shots"
    shots_dir.mkdir(parents=True)
    pending = []
    events = [{"type": "goto", "role": None, "name": None, "value": start_url, "url": start_url}]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        # Binding callbacks only queue events; screenshots are taken in the main loop below.
        page.expose_binding("__shadowEvent", lambda source, ev: pending.append(ev))
        page.add_init_script(LISTENER_JS)
        page.goto(start_url)
        t0_s = time.monotonic()
        events[0]["t_s"] = 0.0
        page.screenshot(path=shots_dir / "000.png")
        events[0]["shot"] = "shots/000.png"
        print("Recording. Do the task, then close the browser window.")
        while not page.is_closed():
            try:
                page.wait_for_timeout(250)
            except PlaywrightError:
                break
            while pending:
                ev = pending.pop(0)
                ev["t_s"] = round(time.monotonic() - t0_s, 2)
                shot = f"shots/{len(events):03d}.png"
                try:
                    page.screenshot(path=run_dir / shot)
                    ev["shot"] = shot
                except PlaywrightError:
                    ev["shot"] = None
                events.append(ev)
                print(f"  {ev['type']:6} {ev['role']} {ev['name']!r} {ev['value'] or ''}")
        browser.close()

    with open(run_dir / "events.jsonl", "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")
    print(f"Saved {len(events)} events to {run_dir}")
    return run_dir


if __name__ == "__main__":
    record(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/demo_site/invoices.html")
