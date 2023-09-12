"""
Test serializers
"""
from unittest.case import TestCase
from unittest.mock import Mock
from uuid import UUID

from ai.api.serializers import CompletionRequestSerializer
from rest_framework import serializers


class CompletionRequestSerializerTest(TestCase):
    def test_validate(self):
        user = Mock(has_seat=False)
        request = Mock(user=user)
        serializer = CompletionRequestSerializer(context={'request': request})
        data = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
        }
        serializer.validate(data)
        self.assertIsNotNone(data['suggestionId'])
        self.assertTrue(isinstance(data['suggestionId'], UUID))

    def test_validate_raises_exception(self):
        user = Mock(has_seat=False)
        request = Mock(user=user)
        serializer = CompletionRequestSerializer(context={'request': request})
        with self.assertRaises(serializers.ValidationError):
            serializer.validate({'prompt': None})
        with self.assertRaises(serializers.ValidationError):
            serializer.validate({'prompt': "---\n"})
        with self.assertRaises(serializers.ValidationError):
            # Prompt does not contain multitask prompt comment or - name:
            serializer.validate({'prompt': "Install Apache\n"})

    def test_validate_multitask_commercial(self):
        user = Mock(has_seat=True)
        request = Mock(user=user)
        serializer = CompletionRequestSerializer(context={'request': request})

        # basic multitask prompt validates without exception
        serializer.validate({'prompt': "#Install SSH\n"})

        # too-many-tasks raises an exception
        with self.assertRaises(serializers.ValidationError):
            serializer.validate({'prompt': "#1&2&3&4&5&6&7&8&9&10&11\n"})

    def test_validate_multitask_no_seat(self):
        user = Mock(has_seat=False)
        request = Mock(user=user)
        serializer = CompletionRequestSerializer(context={'request': request})

        # basic multitask prompt raises exception when no seat
        with self.assertRaises(serializers.ValidationError):
            serializer.validate({'prompt': "#Install SSH\n"})
