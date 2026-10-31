"""End-to-end runner tests against the real demo page, with a fake model in place of Gemma."""
import copy
import functools
import http.server
import json
import threading
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

from shadow.run import run_plan, with_layout

ROOT = Path(__file__).resolve().parent.parent
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

    def run_layout(self, layout, repair):
        page = self.browser.new_page()
        result = run_plan(page, with_layout(self.plan, layout), check=always_ok, repair=repair, log=lambda msg: None)
        status = page.get_by_role("status").text_content()
        page.close()
        return result, status

    def test_layout_a_runs_without_repairs(self):
        result, status = self.run_layout("a", repair=useless_repair)
        self.assertTrue(result["ok"])
        self.assertEqual(result["repairs"], [])
        self.assertEqual(status, "Exported 1 invoice: INV-1042")

    def test_layout_b_is_repaired_and_finishes(self):
        result, status = self.run_layout("b", repair=fake_repair)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["repairs"]), 1)
        self.assertEqual(result["repairs"][0]["step"], 5)
        self.assertEqual(result["plan"]["steps"][4]["target"]["name"], "Download selected")
        self.assertEqual(status, "Exported 1 invoice: INV-1042")

    def test_gives_up_after_repeated_failed_repairs(self):
        result, _ = self.run_layout("b", repair=useless_repair)
        self.assertFalse(result["ok"])
        self.assertEqual(result["failed_step"], 5)


if __name__ == "__main__":
    unittest.main()
