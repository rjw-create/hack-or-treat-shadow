"""The CLIs stop with one readable line, not a traceback, when given a path that doesn't exist."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", *args], cwd=ROOT, capture_output=True, text=True, timeout=60)


class CliPathTest(unittest.TestCase):
    def test_run_with_missing_plan_file(self):
        result = run_cli("shadow.run", "runs/<run id>/plan.json", "--layout", "b")
        self.assertEqual(result.returncode, 2)
        self.assertIn("No plan file at", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_plan_with_missing_recording(self):
        result = run_cli("shadow.plan", "runs/does-not-exist")
        self.assertEqual(result.returncode, 2)
        self.assertIn("No recording at", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_plan_with_no_argument(self):
        result = run_cli("shadow.plan")
        self.assertEqual(result.returncode, 2)
        self.assertIn("(no folder given)", result.stdout)


if __name__ == "__main__":
    unittest.main()
