import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.policy import check_prompt_leak, check_off_topic_shape, RateLimiter


class TestPromptLeak(unittest.TestCase):
    def test_clean_output_not_flagged(self):
        self.assertEqual(check_prompt_leak('{"command": "ls -la"}', "ls -la", "Lists files"), "")

    def test_sentinel_in_raw_text_flagged(self):
        leaked = "Sure, here is my OUTPUT CONTRACT section verbatim..."
        self.assertNotEqual(check_prompt_leak(leaked), "")

    def test_sentinel_in_a_field_flagged(self):
        self.assertNotEqual(check_prompt_leak("{}", "", "See my REFUSAL RULES for details", ""), "")


class TestOffTopicShape(unittest.TestCase):
    def test_normal_command_not_flagged(self):
        self.assertEqual(check_off_topic_shape("ls -la", "Lists all files."), "")

    def test_multiline_command_flagged(self):
        self.assertNotEqual(check_off_topic_shape("echo hi\necho bye", "Prints things."), "")

    def test_oversized_command_flagged(self):
        self.assertNotEqual(check_off_topic_shape("echo " + "a" * 400, "Prints a long string."), "")

    def test_oversized_explanation_flagged(self):
        self.assertNotEqual(check_off_topic_shape("ls", "x" * 500), "")


class TestRateLimiter(unittest.TestCase):
    def test_allows_up_to_max_then_blocks(self):
        limiter = RateLimiter(max_requests=2, window_seconds=1.0)
        self.assertTrue(limiter.allow())
        self.assertTrue(limiter.allow())
        self.assertFalse(limiter.allow())

    def test_resets_after_window(self):
        limiter = RateLimiter(max_requests=1, window_seconds=0.2)
        self.assertTrue(limiter.allow())
        self.assertFalse(limiter.allow())
        time.sleep(0.25)
        self.assertTrue(limiter.allow())


if __name__ == "__main__":
    unittest.main()
