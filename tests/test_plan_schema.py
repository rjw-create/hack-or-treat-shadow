import copy
import json
import unittest
from pathlib import Path

from shadow.steps import PlanError, validate_plan

PLAN = json.loads((Path(__file__).parent / "fixtures" / "plan_export.json").read_text(encoding="utf-8"))


class PlanSchemaTest(unittest.TestCase):
    def broken(self, index, **changes):
        plan = copy.deepcopy(PLAN)
        plan["steps"][index].update(changes)
        return plan

    def test_fixture_is_valid(self):
        validate_plan(PLAN)

    def test_unknown_action_rejected(self):
        with self.assertRaises(PlanError):
            validate_plan(self.broken(4, action="run_python"))

    def test_goto_outside_localhost_rejected(self):
        with self.assertRaises(PlanError):
            validate_plan(self.broken(0, value="https://example.com/payroll"))

    def test_click_without_target_rejected(self):
        with self.assertRaises(PlanError):
            validate_plan(self.broken(4, target=None))

    def test_empty_plan_rejected(self):
        with self.assertRaises(PlanError):
            validate_plan({"steps": []})


if __name__ == "__main__":
    unittest.main()
