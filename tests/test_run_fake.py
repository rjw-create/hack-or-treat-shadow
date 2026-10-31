"""End-to-end runner tests against the real demo page, with a fake model in place of Gemma."""
import copy
import functools
import http.server
import json
import tempfile
import threading
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

from shadow.run import run_plan, save_run, with_layout

ROOT = Path(__file__).resolve().parent.parent
# Shorter than the runner's 3000 ms so fake repairs start sooner. 500 ms was too tight: with a model
# running on the same CPU, a normal page load on layout a timed out and failed the test.
FAST_TIMEOUT_MS = 1500


def action_errors(result):
    return [f"step {s['index']}: {a['error']}" for s in result["log"]["steps"] for a in s["attempts"] if a["error"]]
PLAN = json.loads((ROOT / "tests" / "fixtures" / "plan_export.json").read_text(encoding="utf-8"))


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def always_ok(page, step):
    return True, "fake check"


def fake_repair(page, step, problem):
    """Stands in for the planner: finds the renamed button the way a model reading the tree would."""
    fixed = copy.deepcopy(step)
    fixed["target"]["name"] = "Download selected"
    return fixed, "The Export button was renamed to Download selected and moved below the table."


def dropdown_to_radio_repair(page, step, problem):
    """Layout e: the Status dropdown became radio buttons, so 'select' must become 'click' on a radio."""
    fixed = {"intent": step["intent"], "action": "click", "target": {"role": "radio", "name": step["value"]},
             "expected": step["expected"]}
    return fixed, "The Status dropdown is now a group of radio buttons; click the matching radio instead."


def useless_repair(page, step, problem):
    return copy.deepcopy(step), "No idea."


class RunnerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handler = functools.partial(QuietHandler, directory=str(ROOT))
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        port = cls.server.server_address[1]
        cls.plan = copy.deepcopy(PLAN)
        cls.plan["steps"][0]["value"] = f"http://127.0.0.1:{port}/demo_site/invoices.html"
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()

    def run_layout(self, layout, repair, **kwargs):
        page = self.browser.new_page()
        result = run_plan(page, with_layout(self.plan, layout), check=always_ok, repair=repair, log=lambda msg: None,
                          step_timeout_ms=FAST_TIMEOUT_MS, **kwargs)
        status = page.get_by_role("status").text_content()
        page.close()
        return result, status

    def test_layout_a_runs_without_repairs(self):
        result, status = self.run_layout("a", repair=useless_repair)
        self.assertTrue(result["ok"], action_errors(result))
        self.assertEqual(result["repairs"], [])
        self.assertEqual(status, "Exported 1 invoice: INV-1042")

    def test_layout_b_is_repaired_and_finishes(self):
        result, status = self.run_layout("b", repair=fake_repair)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["repairs"]), 1)
        self.assertEqual(result["repairs"][0]["step"], 5)
        self.assertEqual(result["plan"]["steps"][4]["target"]["name"], "Download selected")
        self.assertEqual(status, "Exported 1 invoice: INV-1042")

    def test_layout_e_repair_switches_select_to_radio(self):
        result, status = self.run_layout("e", repair=dropdown_to_radio_repair)
        self.assertTrue(result["ok"])
        self.assertEqual(result["plan"]["steps"][2]["action"], "click")
        self.assertEqual(result["plan"]["steps"][2]["target"], {"role": "radio", "name": "Unpaid"})
        self.assertEqual(status, "Exported 1 invoice: INV-1042")

    def test_visual_check_runs_on_final_step_and_after_repairs(self):
        visual_calls = []

        def visual_ok(page, step):
            visual_calls.append(step["intent"])
            return True, "fake visual check"

        result, _ = self.run_layout("e", repair=dropdown_to_radio_repair, visual_check=visual_ok)
        self.assertTrue(result["ok"])
        self.assertEqual(visual_calls, ["Show only unpaid invoices", "Export the selected invoice"])
        used = [[a["check"]["used"] for a in s["attempts"] if a["check"]] for s in result["log"]["steps"]]
        self.assertEqual(used, [["check"], ["check"], ["visual_check"], ["check"], ["visual_check"]])

    def test_gives_up_after_repeated_failed_repairs(self):
        result, _ = self.run_layout("b", repair=useless_repair)
        self.assertFalse(result["ok"])
        self.assertEqual(result["failed_step"], 5)
        log = result["log"]
        self.assertEqual(log["steps"][4]["status"], "failed")
        self.assertEqual(len(log["steps"][4]["attempts"]), 3)  # first try plus 2 repairs
        self.assertEqual(log["summary"]["repairs_attempted"], 2)
        self.assertEqual(log["summary"]["repairs_succeeded"], 0)

    def test_run_log_matches_interface(self):
        """Field names and meanings from docs/interface.md, run.json schema_version 1."""
        with tempfile.TemporaryDirectory() as tmp:
            exec_dir = Path(tmp) / "exec" / "test"
            (exec_dir / "shots").mkdir(parents=True)
            page = self.browser.new_page()
            result = run_plan(page, with_layout(self.plan, "b"), check=always_ok, repair=fake_repair,
                              log=lambda msg: None, shots_dir=exec_dir / "shots", step_timeout_ms=FAST_TIMEOUT_MS,
                              run_info={"exec_id": "test", "layout": "b", "models": {"planner": "fake", "checker": "fake"}})
            page.close()
            save_run(exec_dir, result)

            log = json.loads((exec_dir / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(log["schema_version"], 1)
            self.assertTrue(log["ok"])
            self.assertIsNone(log["failed_step"])
            self.assertEqual(log["layout"], "b")
            self.assertEqual([s["status"] for s in log["steps"]], ["passed"] * 4 + ["repaired"])
            last = log["steps"][4]
            first, second = last["attempts"]
            self.assertFalse(first["action_ok"])
            self.assertIsNone(first["check"])
            self.assertTrue(first["repair"]["accepted"])
            self.assertEqual(first["repair"]["new_step"]["target"]["name"], "Download selected")
            self.assertTrue(second["action_ok"] and second["check"]["ok"])
            self.assertEqual(second["screenshot"], "shots/005-2.png")
            self.assertTrue((exec_dir / second["screenshot"]).is_file())
            self.assertIsNone(first["bbox"])
            self.assertEqual(set(second["bbox"]), {"x", "y", "width", "height"})
            self.assertGreater(second["bbox"]["width"], 0)
            self.assertIsNone(log["steps"][0]["attempts"][0]["bbox"])  # goto has no target
            self.assertEqual(log["summary"], {**log["summary"], "steps_total": 5, "steps_passed": 5,
                                              "repairs_attempted": 1, "repairs_succeeded": 1})
            self.assertGreater(log["summary"]["time_per_step_s"], 0)
            self.assertTrue((exec_dir / "automation.py").is_file())
            self.assertTrue((exec_dir / "plan.repaired.json").is_file())


if __name__ == "__main__":
    unittest.main()
