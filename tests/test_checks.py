"""Checker verdict rules, with scripted model replies instead of Gemma (no model or browser needed)."""
import unittest
from unittest import mock

from shadow import run

STEP = {"intent": "Export the selected invoice", "action": "click",
        "target": {"role": "button", "name": "Download selected"},
        "expected": "A message says 1 invoice INV-1042 was exported"}


class FakePage:
    def screenshot(self):
        return b"png"

    def locator(self, selector):
        return self

    def aria_snapshot(self):
        return '- status: "Exported 1 invoice: INV-1042"'


def scripted(*replies):
    """Stand-in for llm.chat_json that returns the given replies in order and records each call."""
    calls = []

    def chat_json(role, prompt, images_png=(), schema=None, think=None, **kwargs):
        calls.append({"role": role, "has_image": bool(images_png), "think": think})
        return replies[len(calls) - 1]
    return chat_json, calls


class CheckVerdictTest(unittest.TestCase):
    def test_no_without_a_contradiction_counts_as_yes(self):
        # The real false negative: the reason quoted the matching text but the verdict was false.
        ok, reason = run.check_verdict({"observed": "Status reads 'Exported 1 invoice: INV-1042'",
                                        "contradiction": "", "ok": False})
        self.assertTrue(ok)
        self.assertIn("Exported 1 invoice", reason)

    def test_none_written_out_counts_as_no_contradiction(self):
        self.assertTrue(run.check_verdict({"observed": "x", "contradiction": "None.", "ok": False})[0])

    def test_named_contradiction_fails_and_is_the_reason(self):
        ok, reason = run.check_verdict({"observed": "Status line is empty",
                                        "contradiction": "No export message is shown", "ok": False})
        self.assertFalse(ok)
        self.assertEqual(reason, "No export message is shown")


class ModelCheckTest(unittest.TestCase):
    def run_check(self, *replies):
        chat_json, calls = scripted(*replies)
        with mock.patch.object(run.llm, "chat_json", chat_json):
            ok, reason = run.model_check(FakePage(), STEP)
        return ok, reason, calls

    def test_screenshot_yes_needs_no_second_opinion(self):
        ok, _, calls = self.run_check({"observed": "Exported 1 invoice: INV-1042", "contradiction": "", "ok": True})
        self.assertTrue(ok)
        self.assertEqual([c["has_image"] for c in calls], [True])

    def test_screenshot_no_overruled_by_text_check(self):
        ok, reason, calls = self.run_check(
            {"observed": "Exported 1 invoice: INV-1042", "contradiction": "Wording differs from expected", "ok": False},
            {"observed": "status: Exported 1 invoice: INV-1042", "contradiction": "", "ok": True})
        self.assertTrue(ok)
        self.assertEqual([c["has_image"] for c in calls], [True, False])
        self.assertIn("Text check passed", reason)
        self.assertIn("Wording differs", reason)  # the overruled screenshot verdict stays visible in run.json

    def test_both_checks_say_no(self):
        ok, reason, _ = self.run_check(
            {"observed": "No message", "contradiction": "No export message is shown", "ok": False},
            {"observed": "status is empty", "contradiction": "Status has no text", "ok": False})
        self.assertFalse(ok)
        self.assertEqual(reason, "No export message is shown")

    def test_checks_run_with_thinking_off(self):
        _, _, calls = self.run_check(
            {"observed": "a", "contradiction": "b", "ok": False},
            {"observed": "c", "contradiction": "d", "ok": False})
        self.assertEqual([c["think"] for c in calls], [False, False])
        self.assertEqual({c["role"] for c in calls}, {"checker"})


class TimeoutTest(unittest.TestCase):
    def test_real_runs_wait_long_enough_under_load(self):
        self.assertGreaterEqual(run.STEP_TIMEOUT_MS, 10000)


if __name__ == "__main__":
    unittest.main()
