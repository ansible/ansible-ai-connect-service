#  Copyright Red Hat
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""
Test post_process
"""

from unittest.case import TestCase

from ansible_ai_connect.ai.api.pipelines.completion_stages import post_process


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
