"""
Test serializers
"""

from unittest.case import TestCase
from unittest.mock import Mock
from uuid import UUID

from django.test import override_settings
from rest_framework import serializers

from ansible_wisdom.ai.api.serializers import (
    CompletionRequestSerializer,
    ContentMatchRequestSerializer,
    ContentMatchSerializer,
    FeedbackRequestSerializer,
    SuggestionQualityFeedback,
)


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

    def test_ignore_empty_model(self):
        user = Mock(rh_user_has_seat=False)
        request = Mock(user=user)
        serializer = CompletionRequestSerializer(context={'request': request})
        data = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "model": "    ",
        }
        serializer.validate(data)
        self.assertIsNone(data.get('model'))

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

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    def test_validate_custom_model_no_seat_with_tech_preview(self):
        user = Mock(rh_user_has_seat=False)
        request = Mock(user=user)
        serializer = CompletionRequestSerializer(
            context={'request': request},
            data={'prompt': "- name: Install SSH\n", 'model': 'custom-model'},
        )

        # model raises exception when no seat
        with self.assertRaises(serializers.ValidationError):
            serializer.is_valid(raise_exception=True)

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=False)
    def test_validate_custom_model_no_seat_without_tech_preview(self):
        user = Mock(rh_user_has_seat=False)
        request = Mock(user=user)
        serializer = CompletionRequestSerializer(
            context={'request': request},
            data={'prompt': "- name: Install SSH\n", 'model': 'custom-model'},
        )

        self.assertTrue(serializer.is_valid())


class ContentMatchRequestSerializerTest(TestCase):
    def test_validate(self):
        serializer = ContentMatchRequestSerializer()
        data = {
            "suggestions": "---\n- hosts: all\n  become: yes\n\n"
            "tasks:\n    - name: Install Apache\n",
            "model": "my-model",
            "suggestionId": "fe0ec82d-e71f-47eb-97da-0a2b32ceb344",
        }
        serializer.validate(data)
        self.assertTrue(data['suggestionId'])

    def test_ignore_empty_model(self):
        serializer = ContentMatchRequestSerializer()
        data = {
            "suggestions": "---\n- hosts: all\n  become: yes\n\n"
            "tasks:\n    - name: Install Apache\n",
            "model": "   ",
            "suggestionId": "fe0ec82d-e71f-47eb-97da-0a2b32ceb344",
        }
        serializer.validate(data)
        self.assertIsNone(data.get("model"))


class ContentMatchSerializerTest(TestCase):
    def test_empty_repo_url_allowed(self):
        data = {
            "repo_url": "",
            "repo_name": "ansible.product_demos",
            "path": "playbooks/infrastructure/aws_provision_vm.yml",
            "license": "gpl-3.0",
            "data_source_description": "Ansible Galaxy collections",
            "score": 0.96241134,
        }
        serializer = ContentMatchSerializer(data=data)
        self.assertTrue(serializer.is_valid())


class SuggestionQualityFeedbackTest(TestCase):
    def test_multitask_prompt_not_stripped(self):
        data = {
            "prompt": "---\n- name: Deploy AWS EC2\n  hosts: localhost\n  tasks:\n"
            "# create vpc & create security group",
            "providedSuggestion": "got this",
            "expectedSuggestion": "wanted this",
            "additionalComment": "p.s.",
        }
        serializer = SuggestionQualityFeedback(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertIn("# create vpc & create security group", serializer.validated_data['prompt'])


class FeedbackRequestSerializerTest(TestCase):
    def test_commercial_user_raises_exception_on_inlineSuggestion(self):
        user = Mock(rh_user_has_seat=True)
        request = Mock(user=user)
        serializer = FeedbackRequestSerializer(
            context={'request': request},
            data={
                "inlineSuggestion": {
                    "latency": 1000,
                    "userActionTime": 5155,
                    "action": "0",
                    "suggestionId": "a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6",
                }
            },
        )

        # inlineSuggestion feedback raises exception when seat
        with self.assertRaises(serializers.ValidationError):
            serializer.is_valid(raise_exception=True)

        # inlineSuggestion feedback raises exception when seat and not telemetry enabled
        with self.assertRaises(serializers.ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_invalid_ansible_extension_version_on_inline_suggestion(self):
        org = Mock(telemetry_opt_out=False)
        user = Mock(rh_user_has_seat=True, organization=org)
        request = Mock(user=user)
        serializer = FeedbackRequestSerializer(
            context={'request': request},
            data={
                "inlineSuggestion": {
                    "latency": 1000,
                    "userActionTime": 5155,
                    "action": "0",
                    "suggestionId": "a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6",
                },
                "metadata": {
                    "ansibleExtensionVersion": "foo",
                },
            },
        )

        # feedback request raises exception when ansibleExtensionVersion is not valid version
        with self.assertRaises(serializers.ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_commercial_user_not_opted_out_passes_on_inlineSuggestion(self):
        org = Mock(telemetry_opt_out=False)
        user = Mock(rh_user_has_seat=True, organization=org)
        request = Mock(user=user)
        serializer = FeedbackRequestSerializer(
            context={'request': request},
            data={
                "inlineSuggestion": {
                    "latency": 1000,
                    "userActionTime": 5155,
                    "action": "0",
                    "suggestionId": "a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6",
                }
            },
        )

        # inlineSuggestion feedback allowed if user seated but not opted Out
        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            self.fail("serializer is_valid should not have raised exception")

    def test_commercial_user_raises_exception_on_ansibleContent(self):
        user = Mock(rh_user_has_seat=True)
        request = Mock(user=user)

        serializer = FeedbackRequestSerializer(
            context={'request': request},
            data={
                "ansibleContent": {
                    "content": "---\n- hosts: all\n  tasks:\n  - name: Install ssh\n",
                    "documentUri": "file:///home/user/ansible/test.yaml",
                    "trigger": "0",
                }
            },
        )

        # ansibleContent feedback raises exception when seat
        with self.assertRaises(serializers.ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_commercial_user_not_opted_out_raises_exception_on_ansibleContent(self):
        org = Mock(telemetry_opt_out=False)
        user = Mock(rh_user_has_seat=True, organization=org)
        request = Mock(user=user)

        serializer = FeedbackRequestSerializer(
            context={'request': request},
            data={
                "ansibleContent": {
                    "content": "---\n- hosts: all\n  tasks:\n  - name: Install ssh\n",
                    "documentUri": "file:///home/user/ansible/test.yaml",
                    "trigger": "0",
                }
            },
        )

        # ansibleContent feedback raises exception when seat
        with self.assertRaises(serializers.ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_commercial_user_allows_sentimentFeedback(self):
        user = Mock(rh_user_has_seat=True)
        request = Mock(user=user)

        serializer = FeedbackRequestSerializer(
            context={'request': request},
            data={"sentimentFeedback": {"value": 3, "feedback": "double meh"}},
        )

        # sentimentFeedback allowed regardless of seat
        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            self.fail("serializer is_valid should not have raised exception")
