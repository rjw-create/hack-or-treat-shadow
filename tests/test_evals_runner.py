"""Eval runner tests: summary math on hand-made records, and the whole suite in fake (pipeline) mode."""
import json
import tempfile
import unittest
from pathlib import Path

from evals.run_evals import FAKE_NOTE, aggregate, run_suite


def record(**overrides):
    base = {"task": "t", "layout": "a", "ok": True, "task_success": True, "repairs_attempted": 0,
            "repairs_succeeded": 0, "attempts": 5, "step_times_s": [1.0, 1.0, 1.0, 1.0, 1.0], "error": None}
    base.update(overrides)
    return base


class AggregateTest(unittest.TestCase):
    def test_rates_and_means(self):
        records = [
            record(),
            record(repairs_attempted=1, repairs_succeeded=1, attempts=6, step_times_s=[2.0, 4.0]),
            record(ok=False, task_success=False, repairs_attempted=2, repairs_succeeded=0, attempts=7,
                   step_times_s=[3.0]),
        ]
        s = aggregate(records)
        self.assertEqual(s["runs"], 3)
        self.assertEqual(s["task_success_rate"], 0.667)
        self.assertEqual(s["repair_success_rate"], 0.333)
        self.assertEqual(s["steps_per_task"], 6)
        # Pooled over all 8 steps that ran, not a mean of per-run means.
        self.assertEqual(s["time_per_step_s"], 1.75)

    def test_no_repairs_gives_no_repair_rate(self):
        self.assertIsNone(aggregate([record()])["repair_success_rate"])


class FakeSuiteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.records, cls.summary, cls.jsonl, cls.summary_path = run_suite("fake", 1, Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def by_layout(self, layout):
        return next(r for r in self.records if r["task"] == "export_invoice" and r["layout"] == layout)

    def test_one_raw_line_per_task_layout_run(self):
        lines = self.jsonl.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), len(self.records))
        self.assertEqual([json.loads(line) for line in lines], self.records)

    def test_layout_a_succeeds_without_repairs(self):
        r = self.by_layout("a")
        self.assertTrue(r["task_success"])
        self.assertTrue(r["end_state_ok"])
        self.assertEqual(r["repairs_attempted"], 0)
        self.assertEqual(r["attempts"], 5)
        self.assertEqual(len(r["step_times_s"]), 5)

    def test_layout_b_succeeds_after_one_repair(self):
        r = self.by_layout("b")
        self.assertTrue(r["task_success"])
        self.assertEqual((r["repairs_attempted"], r["repairs_succeeded"]), (1, 1))
        self.assertEqual(r["attempts_per_step"], [1, 1, 1, 1, 2])

    def test_fake_results_are_labelled_as_pipeline_tests(self):
        self.assertTrue(all(r["note"] == FAKE_NOTE and r["models"]["checker"] == "fake" for r in self.records))
        saved = json.loads(self.summary_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["note"], FAKE_NOTE)
        self.assertIn("-fake-", self.jsonl.name)


if __name__ == "__main__":
    unittest.main()
