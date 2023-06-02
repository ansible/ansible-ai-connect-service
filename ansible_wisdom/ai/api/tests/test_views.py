#!/usr/bin/env python3

import platform
import random
import string
import time
import uuid
from ast import literal_eval
from http import HTTPStatus
from unittest.mock import patch

from ai.api.model_client.base import ModelMeshClient
from ai.api.serializers import AnsibleType, CompletionRequestSerializer, DataSource
from ai.api.views import Completions
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import modify_settings, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITransactionTestCase
from segment import analytics


class DummyMeshClient(ModelMeshClient):
    def __init__(self, test, payload, response_data):
        super().__init__(inference_url='dummy inference url')
        self.test = test

        if "prompt" in payload:
            try:
                serializer = CompletionRequestSerializer()
                data = serializer.validate(payload.copy())

                view = Completions()
                data["context"], data["prompt"] = view.preprocess(
                    data.get("context"), data.get("prompt")
                )

                self.expects = {
                    "instances": [
                        {
                            "context": data.get("context"),
                            "prompt": data.get("prompt"),
                            "userId": str(test.user.uuid),
                            "suggestionId": payload.get("suggestionId"),
                        }
                    ]
                }
            except Exception:  # ignore exception thrown here
                pass

        self.response_data = response_data

    def infer(self, data, model_name=None):
        self.test.assertEqual(data, self.expects)
        time.sleep(0.1)  # w/o this line test_rate_limit() fails...
        # i.e., still receives 200 after 10 API calls...
        return self.response_data


class WisdomServiceAPITestCaseBase(APITransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        analytics.send = False  # do not send data to segment from unit tests

    def setUp(self):
        self.username = 'u' + "".join(random.choices(string.digits, k=5))
        self.password = 'secret'
        email = 'user@example.com'
        self.user = get_user_model().objects.create_user(
            username=self.username,
            email=email,
            password=self.password,
        )
        self.user.user_id = str(uuid.uuid4())
        self.user.date_terms_accepted = timezone.now()
        self.user.save()

        group_1, _ = Group.objects.get_or_create(name='Group 1')
        group_2, _ = Group.objects.get_or_create(name='Group 2')
        group_1.user_set.add(self.user)
        group_2.user_set.add(self.user)
        cache.clear()

    def searchInLogOutput(self, s, logs):
        for log in logs:
            if s in log:
                return True
        return False

    def extractSegmentEventsFromLog(self, logs):
        events = []
        for log in logs:
            if log.startswith('DEBUG:segment:queueing: '):
                obj = literal_eval(
                    log.replace('DEBUG:segment:queueing: ', '')
                    .replace('\n', '')
                    .replace('DataSource.UNKNOWN', '0')
                    .replace('AnsibleType.UNKNOWN', '0')
                )
                events.append(obj)
        return events

    def assertInLog(self, s, logs):
        self.assertTrue(self.searchInLogOutput(s, logs), logs)

    def assertNotInLog(self, s, logs):
        self.assertFalse(self.searchInLogOutput(s, logs), logs)

    def login(self):
        self.client.login(username=self.username, password=self.password)


@modify_settings()
class TestCompletionView(WisdomServiceAPITestCaseBase):
    def test_full_payload(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {"predictions": ["      ansible.builtin.apt:\n        name: apache2"]}
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config('ai'),
            'model_mesh_client',
            DummyMeshClient(self, payload, response_data),
        ):
            r = self.client.post(reverse('completions'), payload)
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertIsNotNone(r.data['predictions'])

    def test_rate_limit(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {"predictions": ["      ansible.builtin.apt:\n        name: apache2"]}
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config('ai'),
            'model_mesh_client',
            DummyMeshClient(self, payload, response_data),
        ):
            r = self.client.post(reverse('completions'), payload)
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertIsNotNone(r.data['predictions'])
            for _ in range(10):
                r = self.client.post(reverse('completions'), payload)
            self.assertEqual(r.status_code, HTTPStatus.TOO_MANY_REQUESTS)

    def test_missing_prompt(self):
        payload = {
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {"predictions": ["      ansible.builtin.apt:\n        name: apache2"]}
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config('ai'),
            'model_mesh_client',
            DummyMeshClient(self, payload, response_data),
        ):
            r = self.client.post(reverse('completions'), payload)
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_authentication_error(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {"predictions": ["      ansible.builtin.apt:\n        name: apache2"]}
        # self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config('ai'),
            'model_mesh_client',
            DummyMeshClient(self, payload, response_data),
        ):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)
                segment_events = self.extractSegmentEventsFromLog(log.output)
                self.assertTrue(len(segment_events) > 0)
                hostname = platform.node()
                for event in segment_events:
                    self.assertEqual(event['userId'], 'unknown')
                    properties = event['properties']
                    self.assertTrue('modelName' in properties)
                    self.assertTrue('imageTags' in properties)
                    self.assertEqual(properties['response']['status_code'], 401)

    def test_completions_preprocessing_error(self):
        payload = {
            "prompt": "---\n- hosts: all\nbecome: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {"predictions": ["      ansible.builtin.apt:\n        name: apache2"]}
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='INFO'):  # Suppress debug output
            with patch.object(
                apps.get_app_config('ai'),
                'model_mesh_client',
                DummyMeshClient(self, payload, response_data),
            ):
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
                self.assertEqual(r.data['message'], 'Request contains invalid yaml')

    def test_completions_preprocessing_error_with_invalid_prompt(self):
        payload = {
            "prompt": "---\n  - name: [Setup]",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {"predictions": ["      ansible.builtin.apt:\n        name: apache2"]}
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='INFO'):  # Suppress debug output
            with patch.object(
                apps.get_app_config('ai'),
                'model_mesh_client',
                DummyMeshClient(self, payload, response_data),
            ):
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
                self.assertEqual(r.data['message'], 'Request contains invalid prompt')

    def test_completions_preprocessing_error_without_name_prompt(self):
        payload = {
            "prompt": "---\n  - Name: [Setup]",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {"predictions": ["      ansible.builtin.apt:\n        name: apache2"]}
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='INFO') as log:  # Suppress debug output
            with patch.object(
                apps.get_app_config('ai'),
                'model_mesh_client',
                DummyMeshClient(self, payload, response_data),
            ):
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
                self.assertInLog("failed to validate request", log.output)
                self.assertTrue("prompt does not contain the name parameter" in str(r.content))

    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_full_payload_without_ARI(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {"predictions": ["      ansible.builtin.apt:\n        name: apache2"]}
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='WARN') as log:
            with patch.object(
                apps.get_app_config('ai'),
                'model_mesh_client',
                DummyMeshClient(self, payload, response_data),
            ):
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data['predictions'])
                self.assertInLog(
                    'skipped ari post processing because ari was not initialized', log.output
                )

    def test_full_payload_with_recommendation_with_broken_last_line(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        # quotation in the last line is not closed, but the truncate function can handle this.
        response_data = {
            "predictions": [
                "      ansible.builtin.apt:\n        name: apache2\n      register: \"test"
            ]
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='INFO') as log:
            with patch.object(
                apps.get_app_config('ai'),
                'model_mesh_client',
                DummyMeshClient(self, payload, response_data),
            ):
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data['predictions'])
                self.assertNotInLog('the recommendation_yaml is not a valid YAML', log.output)

    @override_settings(ENABLE_ARI_POSTPROCESS=True)
    def test_completions_postprocessing_error(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "predictions": ["      ansible.builtin.apt:\n garbage       name: apache2"]
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='ERROR') as log:  # Suppress debug output
            with patch.object(
                apps.get_app_config('ai'),
                'model_mesh_client',
                DummyMeshClient(self, payload, response_data),
            ):
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(HTTPStatus.NO_CONTENT, r.status_code)
                self.assertEqual(None, r.data)
                self.assertInLog('error postprocessing prediction for suggestion', log.output)

    def test_completions_pii_clean_up(self):
        payload = {
            "prompt": "- name: Create an account for foo@ansible.com \n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {"predictions": [""]}
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='DEBUG') as log:
            with patch.object(
                apps.get_app_config('ai'),
                'model_mesh_client',
                DummyMeshClient(self, payload, response_data),
            ):
                r = self.client.post(reverse('completions'), payload)
                self.assertInLog('Create an account for james8@example.com', log.output)

    def test_full_completion_post_response(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config('ai'),
            'model_mesh_client',
            DummyMeshClient(self, payload, response_data),
        ):
            r = self.client.post(reverse('completions'), payload)
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertIsNotNone(r.data['predictions'])
            self.assertIsNotNone(r.data['modelName'])
            self.assertIsNotNone(r.data['suggestionId'])


@modify_settings()
class TestFeedbackView(WisdomServiceAPITestCaseBase):
    def test_feedback_full_payload(self):
        payload = {
            "inlineSuggestion": {
                "latency": 1000,
                "userActionTime": 3500,
                "documentUri": "file:///home/user/ansible.yaml",
                "action": "0",
                "suggestionId": str(uuid.uuid4()),
            },
            "ansibleContent": {
                "content": "---\n- hosts: all\n  become: yes\n\n  "
                "tasks:\n    - name: Install Apache\n",
                "documentUri": "file:///home/user/ansible.yaml",
                "activityId": str(uuid.uuid4()),
                "trigger": "0",
            },
        }
        self.client.force_authenticate(user=self.user)
        r = self.client.post(reverse('feedback'), payload, format='json')
        self.assertEqual(r.status_code, HTTPStatus.OK)

    def test_missing_content(self):
        payload = {
            "ansibleContent": {"documentUri": "file:///home/user/ansible.yaml", "trigger": "0"}
        }
        self.client.force_authenticate(user=self.user)
        r = self.client.post(reverse('feedback'), payload, format="json")
        self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

    def test_anonymize(self):
        payload = {
            "ansibleContent": {
                "content": "---\n- hosts: all\n  become: yes\n\n  "
                "tasks:\n    - name: Install Apache\n",
                "documentUri": "file:///home/jean-pierre/ansible.yaml",
                "trigger": "0",
            }
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(reverse('feedback'), payload, format="json")
            self.assertNotInLog('file:///home/user/ansible.yaml', log.output)
            self.assertInLog('file:///home/ano-user/ansible.yaml', log.output)

    def test_authentication_error(self):
        payload = {
            "ansibleContent": {
                "content": "---\n- hosts: all\n  become: yes\n\n  "
                "tasks:\n    - name: Install Apache\n",
                "documentUri": "file:///home/user/ansible.yaml",
                "trigger": "0",
            }
        }
        # self.client.force_authenticate(user=self.user)
        r = self.client.post(reverse('feedback'), payload, format="json")
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_feedback_segment_events(self):
        payload = {
            "inlineSuggestion": {
                "latency": 1000,
                "userActionTime": 3500,
                "documentUri": "file:///home/user/ansible.yaml",
                "action": "0",
                "suggestionId": str(uuid.uuid4()),
            },
            "ansibleContent": {
                "content": "---\n- hosts: all\n  become: yes\n\n  "
                "tasks:\n    - name: Install Apache\n",
                "documentUri": "file:///home/user/ansible.yaml",
                "activityId": str(uuid.uuid4()),
                "trigger": "0",
            },
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(reverse('feedback'), payload, format='json')
            self.assertEqual(r.status_code, HTTPStatus.OK)

            segment_events = self.extractSegmentEventsFromLog(log.output)
            self.assertTrue(len(segment_events) > 0)
            hostname = platform.node()
            for event in segment_events:
                properties = event['properties']
                self.assertTrue('modelName' in properties)
                self.assertTrue('imageTags' in properties)
                self.assertTrue('groups' in properties)
                self.assertTrue('Group 1' in properties['groups'])
                self.assertTrue('Group 2' in properties['groups'])
                self.assertEqual(hostname, properties['hostname'])

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_feedback_segment_inline_suggestion_feedback_error(self):
        payload = {
            "inlineSuggestion": {
                "latency": 1000,
                "userActionTime": 3500,
                "documentUri": "file:///home/rbobbitt/ansible.yaml",
                "action": "2",  # invalid choice for action
                "suggestionId": str(uuid.uuid4()),
            }
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(reverse('feedback'), payload, format='json')
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

            segment_events = self.extractSegmentEventsFromLog(log.output)
            self.assertTrue(len(segment_events) > 0)
            for event in segment_events:
                self.assertTrue('inlineSuggestionFeedback', event['event'])
                properties = event['properties']
                self.assertTrue('data' in properties)
                self.assertTrue('exception' in properties)
                self.assertEqual(
                    "file:///home/ano-user/ansible.yaml",
                    properties['data']['inlineSuggestion']['documentUri'],
                )

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_feedback_segment_ansible_content_feedback_error(self):
        payload = {
            "ansibleContent": {
                "content": "---\n- hosts: all\n  become: yes\n\n  "
                "tasks:\n    - name: Install Apache\n",
                "documentUri": "file:///home/rbobbitt/ansible.yaml",
                "activityId": "123456",  # an invalid UUID
                "trigger": "0",
            }
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(reverse('feedback'), payload, format='json')
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

            segment_events = self.extractSegmentEventsFromLog(log.output)
            self.assertTrue(len(segment_events) > 0)
            for event in segment_events:
                self.assertTrue('ansibleContentFeedback', event['event'])
                properties = event['properties']
                self.assertTrue('data' in properties)
                self.assertTrue('exception' in properties)
                self.assertEqual(
                    "file:///home/ano-user/ansible.yaml",
                    properties['data']['ansibleContent']['documentUri'],
                )


class TestAttributionsView(WisdomServiceAPITestCaseBase):
    @patch('ai.search.search')
    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_segment_events(self, mock_search):
        mock_search.return_value = {
            'attributions': [
                {
                    'repo_name': 'repo_name',
                    'repo_url': 'http://example.com',
                    'path': '/path',
                    'license': 'license',
                    'data_source': DataSource.UNKNOWN,
                    'ansible_type': AnsibleType.UNKNOWN,
                    'score': 0.0,
                },
            ],
            'meta': {
                'encode_duration': 1000,
                'search_duration': 2000,
            },
        }
        payload = {
            'suggestion': 'suggestion',
            'suggestionId': str(uuid.uuid4()),
        }

        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(reverse('attributions'), payload, format='json')
            self.assertEqual(r.status_code, HTTPStatus.OK)

            segment_events = self.extractSegmentEventsFromLog(log.output)
            self.assertTrue(len(segment_events) > 0)
            hostname = platform.node()
            for event in segment_events:
                properties = event['properties']
                self.assertTrue('modelName' in properties)
                self.assertTrue('imageTags' in properties)
                self.assertTrue('groups' in properties)
                self.assertTrue('Group 1' in properties['groups'])
                self.assertTrue('Group 2' in properties['groups'])
                self.assertEqual(hostname, properties['hostname'])

    @patch('ai.search.search')
    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_segment_events_with_exception(self, mock_search):
        mock_search.side_effect = Exception('Search Exception')
        payload = {
            'suggestion': 'suggestion',
            'suggestionId': str(uuid.uuid4()),
        }

        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(reverse('attributions'), payload, format='json')
            self.assertEqual(r.status_code, HTTPStatus.SERVICE_UNAVAILABLE)

            segment_events = self.extractSegmentEventsFromLog(log.output)
            self.assertEqual(len(segment_events), 0)
            self.assertInLog('Failed to search for attributions', log.output)
