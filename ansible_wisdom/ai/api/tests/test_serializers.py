"""
Test serializers
"""
from unittest.case import TestCase

from ai.api.serializers import CompletionRequestSerializer


class CompletionRequestSerializerTest(TestCase):
    def run_a_test(self, prompt_in, context_expected, prompt_expected):
        data = {}
        data['prompt'] = prompt_in
        CompletionRequestSerializer.extract_prompt_and_context(data)
        self.assertEqual(prompt_expected, data['prompt'])
        self.assertEqual(context_expected, data['context'])

    def test_get_instances_from_payload(self):
        PROMPT_IN = '---\n- hosts: all\n  become: yes\n\n  tasks:\n  - name: Install Apache\n'
        CONTEXT_OUT = "---\n- hosts: all\n  become: yes\n\n  tasks:\n"
        PROMPT_OUT = "  - name: Install Apache\n"

        self.run_a_test(PROMPT_IN, CONTEXT_OUT, PROMPT_OUT)
        self.run_a_test('', '', '')
        self.run_a_test(None, '', '')
        self.run_a_test('---\n', '---\n', '')
