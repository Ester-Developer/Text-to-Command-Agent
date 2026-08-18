import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.converter import convert


def _fake_llm_response(**overrides):
    base = {
        "command": "dir",
        "explanation": "Lists the files and folders in the current directory.",
        "os": "Windows (cmd.exe)",
        "risk_level": "low",
        "safe": True,
        "refused": False,
        "refusal_reason": "",
    }
    base.update(overrides)
    return json.dumps(base)


class TestConverter(unittest.TestCase):
    def test_high_risk_never_shown_as_safe_to_run(self):
        # Regression test: observed live that a nonsense instruction made
        # the model return a self-contradictory response (risk_level=high,
        # safe=true, not refused). final_safe_to_show_as_runnable must
        # reject "high" risk_level regardless of the model's own safe flag.
        response = _fake_llm_response(risk_level="high", safe=True, refused=False)
        with patch("src.llm_client.complete", return_value=response):
            result = convert("asdkj qwoiu banana purple 42", os_name="Windows (cmd.exe)")
        self.assertFalse(result.final_safe_to_show_as_runnable)

    def test_low_risk_safe_command_is_runnable(self):
        response = _fake_llm_response(risk_level="low", safe=True, refused=False)
        with patch("src.llm_client.complete", return_value=response):
            result = convert("list files", os_name="linux/macOS (bash)")
        self.assertTrue(result.final_safe_to_show_as_runnable)

    def test_medium_risk_safe_command_is_runnable(self):
        response = _fake_llm_response(command="rm temp.log", risk_level="medium", safe=True, refused=False)
        with patch("src.llm_client.complete", return_value=response):
            result = convert("delete temp.log", os_name="linux/macOS (bash)")
        self.assertTrue(result.final_safe_to_show_as_runnable)


if __name__ == "__main__":
    unittest.main()
