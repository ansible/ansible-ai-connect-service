"""
Test serializers
"""
from unittest.case import TestCase

from rest_framework.exceptions import APIException

from .serializers import CompletionRequestSerializer, CompletionResponseSerializer


class CompletionRequestSerializerTest(TestCase):
    def run_a_test(self, context_in, prompt_in, context_expected, prompt_expected):
        data = {}
        if context_in is not None:
            data['context'] = context_in
        if prompt_in is not None:
            data['prompt'] = prompt_in
        CompletionRequestSerializer.extract_prompt_from_context(data)
        self.assertEqual(prompt_expected, data['prompt'])
        self.assertEqual(context_expected, data['context'])

    def test_get_instances_from_payload(self):
        CONTEXT_OLD = '---\n- hosts: all\n  become: yes\n\n  tasks:\n'
        PROMPT = '- name: Install Apache\n'
        CONTEXT_NEW = CONTEXT_OLD + '    ' + PROMPT

        self.run_a_test(CONTEXT_OLD, PROMPT, CONTEXT_OLD, PROMPT)
        self.run_a_test(CONTEXT_NEW, None, CONTEXT_OLD, PROMPT)
        self.run_a_test('', '', '', '')
        self.run_a_test('', None, '', '')
        self.run_a_test('---\n', None, '---\n', '')

    def test_is_valid_response(self):
        VALID_DATA = {
            'predictions': ['  ansible.builtin.yum:\n    name: httpd\n    state: present\n']
        }
        serializer = CompletionResponseSerializer(data=VALID_DATA)
        serializer.is_valid()  # raise_exception=False
        serializer.is_valid(raise_exception=True)

        INVALID_DATA = {}
        serializer = CompletionResponseSerializer(data=INVALID_DATA)
        serializer.is_valid()  # raise_exception=False

        # Expect an APIException that will return a 500 will be raised
        # for an invalid data.
        with self.assertRaises(APIException):
            serializer.is_valid(raise_exception=True)
