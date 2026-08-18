import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.syntax_validator import check_syntax


class TestSyntaxValidator(unittest.TestCase):
    def test_valid_simple_command(self):
        self.assertTrue(check_syntax("ls -la").valid)

    def test_valid_quoted_argument(self):
        self.assertTrue(check_syntax('find . -name "*.py"').valid)

    def test_empty_command_invalid(self):
        self.assertFalse(check_syntax("").valid)
        self.assertFalse(check_syntax("   ").valid)

    def test_unbalanced_double_quotes(self):
        self.assertFalse(check_syntax('echo "unterminated').valid)

    def test_unbalanced_single_quotes(self):
        self.assertFalse(check_syntax("echo 'unterminated").valid)

    def test_dangling_pipe(self):
        self.assertFalse(check_syntax("ls |").valid)

    def test_dangling_and(self):
        self.assertFalse(check_syntax("ls &&").valid)

    def test_leading_pipe_invalid(self):
        self.assertFalse(check_syntax("| ls").valid)


if __name__ == "__main__":
    unittest.main()
