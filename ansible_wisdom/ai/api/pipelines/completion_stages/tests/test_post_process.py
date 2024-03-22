"""
Test post_process
"""

from unittest.case import TestCase

from ansible_wisdom.ai.api.pipelines.completion_stages import post_process


class TrimWhitespaceLinesTest(TestCase):
    def test_empty_string(self):
        self.assertEqual(post_process.trim_whitespace_lines(""), "")

    def test_whitespace_in_beginning(self):
        self.assertEqual(
            post_process.trim_whitespace_lines("   \nhello\ngoodbye"), "\nhello\ngoodbye"
        )

    def test_whitespace_in_middle(self):
        self.assertEqual(
            post_process.trim_whitespace_lines("hello\n    \ngoodbye"), "hello\n\ngoodbye"
        )

    def test_whitespace_in_end(self):
        self.assertEqual(
            post_process.trim_whitespace_lines("hello\ngoodbye\n   "), "hello\ngoodbye\n"
        )
