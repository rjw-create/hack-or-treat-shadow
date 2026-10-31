import ast
import copy
import json
import unittest
from pathlib import Path

from shadow.compile import compile_plan

PLAN = json.loads((Path(__file__).parent / "fixtures" / "plan_export.json").read_text(encoding="utf-8"))


class CompileTest(unittest.TestCase):
    def test_output_is_valid_python_with_semantic_selectors(self):
        code = compile_plan(PLAN)
        ast.parse(code)
        self.assertIn("page.get_by_role('button', name='Export selected', exact=True).click()", code)
        self.assertIn("page.get_by_role('checkbox', name='Select INV-1042', exact=True).check()", code)
        self.assertIn(".select_option(label='Unpaid')", code)

    def test_hostile_text_stays_inside_string_literals(self):
        plan = copy.deepcopy(PLAN)
        hostile = "x'); import os; os.system('calc'); ('"
        plan["steps"][4]["target"]["name"] = hostile
        plan["steps"][4]["intent"] = "Export\nimport os"
        tree = ast.parse(compile_plan(plan))
        imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
        self.assertEqual(len(imports), 1)  # only the header's playwright import
        strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)]
        self.assertIn(hostile, strings)


if __name__ == "__main__":
    unittest.main()
