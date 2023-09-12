"""
Test serializers
"""
from unittest.case import TestCase
from uuid import UUID

from ai.api.serializers import CompletionRequestSerializer
from rest_framework import serializers


class CompletionRequestSerializerTest(TestCase):
    def test_validate(self):
        serializer = CompletionRequestSerializer()
        data = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
        }
        serializer.validate(data)
        self.assertIsNotNone(data['suggestionId'])
        self.assertTrue(isinstance(data['suggestionId'], UUID))

    def test_validate_raises_exception(self):
        with self.assertRaises(serializers.ValidationError):
            serializer = CompletionRequestSerializer()
            serializer.validate({'prompt': None})
        with self.assertRaises(serializers.ValidationError):
            serializer = CompletionRequestSerializer()
            serializer.validate({'prompt': "---\n"})
        with self.assertRaises(serializers.ValidationError):
            # Prompt does not contain multitask prompt comment or - name:
            serializer = CompletionRequestSerializer()
            serializer.validate({'prompt': "Install Apache\n"})
