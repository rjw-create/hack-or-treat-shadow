"""Eval runner tests: summary math on hand-made records, and the whole suite in fake (pipeline) mode."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from evals.run_evals import FAKE_NOTE, ROOT, aggregate, run_suite, select


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


class SelectTest(unittest.TestCase):
    SUITE = {"tasks": [{"id": "t1", "layouts": ["a", "b", "e"]}, {"id": "t2", "layouts": ["a", "c"]}]}

    def test_keeps_only_named_tasks_and_layouts(self):
        picked = select(self.SUITE, tasks=["t1"], layouts=["a", "e"])
        self.assertEqual(picked["tasks"], [{"id": "t1", "layouts": ["a", "e"]}])

    def test_drops_tasks_left_with_no_layouts(self):
        self.assertEqual([t["id"] for t in select(self.SUITE, layouts=["c"])["tasks"]], ["t2"])

    def test_unknown_names_are_an_error(self):
        with self.assertRaises(ValueError):
            select(self.SUITE, tasks=["export_invoce"])


class SavedRunsTest(unittest.TestCase):
    """What --show adds besides the headed browser: one exec folder per run that viewer.report can open."""

    def test_saved_run_folder_opens_in_the_viewer(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            records, *_ = run_suite("fake", 1, tmp / "results", tasks=["export_invoice"], layouts=["b"],
                                    runs_dir=tmp / "runs")
            exec_dir = tmp / records[0]["exec_dir"]
            log = json.loads((exec_dir / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(log["exec_id"], exec_dir.name)
            self.assertTrue((exec_dir / "plan.repaired.json").exists())
            shot = log["steps"][4]["attempts"][1]["screenshot"]
            self.assertTrue((exec_dir / shot).exists())
            viewer = subprocess.run([sys.executable, "-m", "viewer.report", str(exec_dir)],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(viewer.returncode, 0, viewer.stderr)
            self.assertTrue((exec_dir / "report.html").exists())


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

    def test_every_task_and_layout_succeeds_with_the_oracle(self):
        # Proves the suite file itself is right: each layout's answer key really fixes that layout.
        self.assertEqual(len(self.records), 15)
        failed = [(r["task"], r["layout"]) for r in self.records if not r["task_success"]]
        self.assertEqual(failed, [])

    def test_layout_e_repair_switches_dropdown_to_radio(self):
        step3 = self.by_layout("e")["run_log"]["steps"][2]
        self.assertEqual(step3["status"], "repaired")
        new_step = step3["attempts"][0]["repair"]["new_step"]
        self.assertEqual(new_step["action"], "click")
        self.assertEqual(new_step["target"], {"role": "radio", "name": "Unpaid"})
        self.assertNotIn("value", new_step)

    def test_raw_line_embeds_the_run_log(self):
        log = self.by_layout("b")["run_log"]
        self.assertEqual(log["schema_version"], 1)
        self.assertEqual(log["layout"], "b")
        self.assertEqual(log["models"], {"planner": "fake", "checker": "fake"})
        self.assertEqual(log["summary"]["repairs_succeeded"], 1)

    def test_fake_results_are_labelled_as_pipeline_tests(self):
        self.assertTrue(all(r["note"] == FAKE_NOTE and r["models"]["checker"] == "fake" for r in self.records))
        saved = json.loads(self.summary_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["note"], FAKE_NOTE)
        self.assertIn("-fake-", self.jsonl.name)


if __name__ == "__main__":
    unittest.main()
