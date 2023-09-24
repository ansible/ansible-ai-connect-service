"""
Test serializers
"""
from unittest.case import TestCase
from unittest.mock import Mock
from uuid import UUID

from ai.api.serializers import CompletionRequestSerializer
from django.test import override_settings
from rest_framework import serializers


class CompletionRequestSerializerTest(TestCase):
    def test_validate(self):
        user = Mock(rh_user_has_seat=False)
        request = Mock(user=user)
        serializer = CompletionRequestSerializer(context={'request': request})
        data = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
        }
        serializer.validate(data)
        self.assertIsNotNone(data['suggestionId'])
        self.assertTrue(isinstance(data['suggestionId'], UUID))

    def test_validate_raises_exception(self):
        user = Mock(rh_user_has_seat=False)
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
        user = Mock(rh_user_has_seat=True)
        request = Mock(user=user)
        serializer = CompletionRequestSerializer(context={'request': request})

        # basic multitask prompt validates without exception
        serializer.validate({'prompt': "#Install SSH\n"})

        # too-many-tasks raises an exception
        with self.assertRaises(serializers.ValidationError):
            serializer.validate({'prompt': "#1&2&3&4&5&6&7&8&9&10&11\n"})

        # multiple && raises an exception
        with self.assertRaises(serializers.ValidationError):
            serializer.validate({'prompt': "#install ssh && start ssh\n"})

    @override_settings(MULTI_TASK_MAX_REQUESTS=3)
    def test_validate_max_multitask_requests_setting(self):
        user = Mock(rh_user_has_seat=True)
        request = Mock(user=user)
        serializer = CompletionRequestSerializer(context={'request': request})

        # two tasks multitask prompt validates without exception
        serializer.validate({'prompt': "#Install SSH & start service\n"})

        # too-many-tasks raises an exception
        with self.assertRaises(serializers.ValidationError):
            serializer.validate({'prompt': "#1&2&3&4\n"})

    def test_validate_multitask_no_seat(self):
        user = Mock(rh_user_has_seat=False)
        request = Mock(user=user)
        serializer = CompletionRequestSerializer(context={'request': request})

        # basic multitask prompt raises exception when no seat
        with self.assertRaises(serializers.ValidationError):
            serializer.validate({'prompt': "#Install SSH\n"})
