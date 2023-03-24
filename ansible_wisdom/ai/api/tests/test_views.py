#!/usr/bin/env python3

import random
import string
import time
import uuid
from datetime import datetime
from http import HTTPStatus
from unittest.mock import patch

from ai.api.model_client.base import ModelMeshClient
from ai.api.serializers import CompletionRequestSerializer
from ai.api.views import Completions
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import modify_settings, override_settings
from django.urls import reverse
from rest_framework.response import Response
from rest_framework.test import APITransactionTestCase
from yaml.parser import ParserError

WISDOM_API_VERSION = "v0"


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
            except ParserError:  # ignore YAML parser errors thrown here
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
        cls.username = 'u' + "".join(random.choices(string.digits, k=5))
        cls.password = 'secret'
        cls.email = 'user@example.com'
        cls.user = get_user_model().objects.create_user(
            username=cls.username,
            email=cls.email,
            password=cls.password,
        )
        cls.user.user_id = str(uuid.uuid4())
        cls.user.date_terms_accepted = datetime.now()

    def setUp(self):
        cache.clear()

    def searchInLogOutput(self, s, logs):
        for log in logs:
            if s in log:
                return True
        return False

    def assertInLog(self, s, logs):
        self.assertTrue(self.searchInLogOutput(s, logs))

    def assertNotInLog(self, s, logs):
        self.assertFalse(self.searchInLogOutput(s, logs))

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
            r = self.client.post(reverse(f'{WISDOM_API_VERSION}:completions'), payload)
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
            r = self.client.post(reverse(f'{WISDOM_API_VERSION}:completions'), payload)
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertIsNotNone(r.data['predictions'])
            for _ in range(10):
                r = self.client.post(reverse(f'{WISDOM_API_VERSION}:completions'), payload)
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
            r = self.client.post(reverse(f'{WISDOM_API_VERSION}:completions'), payload)
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

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
            r = self.client.post(reverse(f'{WISDOM_API_VERSION}:completions'), payload)
            self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)


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
        r = self.client.post(reverse(f'{WISDOM_API_VERSION}:feedback'), payload, format='json')
        self.assertEqual(r.status_code, HTTPStatus.OK)

    def test_missing_content(self):
        payload = {
            "ansibleContent": {"documentUri": "file:///home/user/ansible.yaml", "trigger": "0"}
        }
        self.client.force_authenticate(user=self.user)
        r = self.client.post(reverse(f'{WISDOM_API_VERSION}:feedback'), payload, format="json")
        self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

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
        r = self.client.post(reverse(f'{WISDOM_API_VERSION}:feedback'), payload, format="json")
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

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
                r = self.client.post(reverse(f'{WISDOM_API_VERSION}:completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

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
            ), patch.object(
                apps.get_app_config('ai'),
                'ari_caller',
                None,
            ):
                r = self.client.post(reverse(f'{WISDOM_API_VERSION}:completions'), payload)
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
                r = self.client.post(reverse(f'{WISDOM_API_VERSION}:completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data['predictions'])
                self.assertNotInLog('the recommendation_yaml is not a valid YAML', log.output)

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
                r = self.client.post(reverse(f'{WISDOM_API_VERSION}:completions'), payload)
                self.assertEqual(HTTPStatus.NO_CONTENT, r.status_code)
                self.assertEqual(None, r.data)
                self.assertInLog('error postprocessing prediction for suggestion', log.output)
