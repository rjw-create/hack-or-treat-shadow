"""Viewer report tests: model-written text is escaped and screenshot paths cannot leave the exec folder."""
import json
import unittest
from pathlib import Path

from viewer.report import render

FIXTURES = Path(__file__).resolve().parent.parent / "viewer" / "fixtures"


def load(name):
    folder = FIXTURES / name
    return json.loads((folder / "run.json").read_text(encoding="utf-8")), folder


class ReportTest(unittest.TestCase):
    def test_repaired_run_shows_every_step_and_the_repair(self):
        run, folder = load("repaired_run")
        page = render(run, folder)
        for i in range(1, 6):
            self.assertIn(f'id="step-{i}"', page)
        self.assertIn("Run passed", page)
        self.assertIn("<del>click button &quot;Export selected&quot;</del>", page)
        self.assertIn("<ins>click button &quot;Download selected&quot;</ins>", page)
        self.assertIn('src="shots/005-2.png"', page)

    def test_model_text_is_escaped(self):
        run, folder = load("failed_run")
        page = render(run, folder)
        self.assertNotIn("<script>alert", page)
        self.assertNotIn("<img src=x", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)

    def test_screenshot_paths_outside_shots_are_dropped(self):
        run, folder = load("failed_run")
        page = render(run, folder)
        self.assertNotIn("secret.png", page)
        self.assertNotIn('href="javascript:', page)

    def test_bbox_is_drawn_in_percent_of_the_screenshot(self):
        run, folder = load("repaired_run")
        page = render(run, folder)
        # 470/640 px and 330/400 px in the 640x400 placeholder screenshot.
        self.assertIn('style="left:73.438%;top:82.500%;width:23.438%;height:8.500%"', page)

    def test_non_numeric_bbox_is_dropped(self):
        run, folder = load("failed_run")
        page = render(run, folder)
        self.assertNotIn('class="bbox', page)
        self.assertNotIn("example.com", page)

    def test_check_kind_is_labelled(self):
        run, folder = load("repaired_run")
        page = render(run, folder)
        self.assertEqual(page.count("Text check <span"), 4)
        self.assertEqual(page.count("Screenshot check <span"), 1)
        failed_page = render(*load("failed_run"))
        self.assertIn('Check <span class="bad">failed</span>', failed_page)

    def test_missing_recording_is_not_shown_as_none(self):
        run, folder = load("failed_run")
        self.assertNotIn("of recording", render(run, folder))

    def test_failed_run_states(self):
        run, folder = load("failed_run")
        page = render(run, folder)
        self.assertIn("Run failed at step 2", page)
        self.assertIn("rejected (failed validation)", page)
        self.assertIn("Screenshot missing", page)
        self.assertIn("This step was not reached.", page)


if __name__ == "__main__":
    unittest.main()
