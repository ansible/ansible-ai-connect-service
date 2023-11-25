#!/usr/bin/env python3

import json
import platform
import random
import string
import time
import uuid
from http import HTTPStatus
from unittest.mock import Mock, patch

import requests
from ai.api.data.data_model import APIPayload
from ai.api.model_client.base import ModelMeshClient
from ai.api.model_client.exceptions import (
    ModelTimeoutError,
    WcaBadRequest,
    WcaCloudflareRejection,
    WcaEmptyResponse,
    WcaException,
    WcaInvalidModelId,
    WcaKeyNotFound,
    WcaModelIdNotFound,
)
from ai.api.model_client.tests.test_wca_client import (
    WCA_REQUEST_ID_HEADER,
    MockResponse,
)
from ai.api.model_client.wca_client import WCAClient
from ai.api.pipelines.completion_context import CompletionContext
from ai.api.pipelines.completion_stages.inference import get_model_client
from ai.api.pipelines.completion_stages.post_process import trim_whitespace_lines
from ai.api.pipelines.completion_stages.pre_process import completion_pre_process
from ai.api.pipelines.completion_stages.response import CompletionsPromptType
from ai.api.serializers import AnsibleType, CompletionRequestSerializer, DataSource
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import modify_settings, override_settings
from django.urls import reverse
from django.utils import timezone
from requests.exceptions import ReadTimeout
from rest_framework.test import APITransactionTestCase
from segment import analytics
from test_utils import WisdomLogAwareMixin, WisdomServiceLogAwareTestCase

DEFAULT_SUGGESTION_ID = uuid.uuid4()


class DummyMeshClient(ModelMeshClient):
    def __init__(
        self, test, payload, response_data, test_inference_match=True, rh_user_has_seat=False
    ):
        super().__init__(inference_url='dummy inference url')
        self.test = test
        self.test_inference_match = test_inference_match

        if "prompt" in payload:
            try:
                user = Mock(rh_user_has_seat=rh_user_has_seat)
                request = Mock(user=user)
                serializer = CompletionRequestSerializer(context={'request': request})
                data = serializer.validate(payload.copy())

                context = CompletionContext(
                    request=request,
                    payload=APIPayload(prompt=data.get("prompt"), context=data.get("context")),
                )
                completion_pre_process(context)

                self.expects = {
                    "instances": [
                        {
                            "context": context.payload.context,
                            "prompt": context.payload.prompt,
                            "userId": str(test.user.uuid),
                            "rh_user_has_seat": rh_user_has_seat,
                            "organization_id": None,
                            "suggestionId": payload.get("suggestionId"),
                        }
                    ]
                }
            except Exception:  # ignore exception thrown here
                pass

        self.response_data = response_data

    def infer(self, data, model_id=None, suggestion_id=None):
        if self.test_inference_match:
            self.test.assertEqual(data, self.expects)
        time.sleep(0.1)  # w/o this line test_rate_limit() fails...
        # i.e., still receives 200 after 10 API calls...
        return self.response_data


class WisdomServiceAPITestCaseBase(APITransactionTestCase, WisdomServiceLogAwareTestCase):
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
        self.user.community_terms_accepted = timezone.now()
        self.user.save()

        group_1, _ = Group.objects.get_or_create(name='Group 1')
        group_2, _ = Group.objects.get_or_create(name='Group 2')
        group_1.user_set.add(self.user)
        group_2.user_set.add(self.user)
        cache.clear()

    def login(self):
        self.client.login(username=self.username, password=self.password)


@override_settings(WCA_CLIENT_BACKEND_TYPE="wcaclient")
@modify_settings()
class TestCompletionWCAView(WisdomServiceAPITestCaseBase):
    def stub_wca_client(self, status_code, mock_api_key, mock_model_id, suggestion_id: uuid):
        model_input = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(suggestion_id),
        }
        response = MockResponse(
            json={"predictions": [""]},
            status_code=status_code,
            headers={WCA_REQUEST_ID_HEADER: str(suggestion_id)},
        )
        model_client = WCAClient(inference_url='https://wca_api_url')
        model_client.session.post = Mock(return_value=response)
        model_client.get_api_key = mock_api_key
        model_client.get_model_id = mock_model_id
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        return model_client, model_input

    def test_seated_got_wca(self):
        self.user.rh_user_has_seat = True
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)
        model_client, model_name = get_model_client(apps.get_app_config('ai'), self.user)
        self.assertTrue(isinstance(model_client, WCAClient))
        self.assertIsNone(model_name)

    def test_seatless_got_no_wca(self):
        self.user.rh_user_has_seat = False
        self.client.force_authenticate(user=self.user)
        model_client, model_name = get_model_client(apps.get_app_config('ai'), self.user)
        self.assertFalse(isinstance(model_client, WCAClient))
        self.assertIsNone(model_name)

    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_wca_completion(self):
        self.user.rh_user_has_seat = True
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            200,
            Mock(return_value='org-api-key'),
            Mock(return_value='org-model-id'),
            DEFAULT_SUGGESTION_ID,
        )
        model_client, model_input = stub
        with patch.object(apps.get_app_config('ai'), '_wca_client', model_client):
            r = self.client.post(reverse('completions'), model_input)
            self.assertEqual(r.status_code, HTTPStatus.OK)
            model_client.get_token.assert_called_once()
            self.assertEqual(
                model_client.session.post.call_args.args[0],
                "https://wca_api_url/v1/wca/codegen/ansible",
            )
            self.assertEqual(
                model_client.session.post.call_args.kwargs['json']['model_id'], 'org-model-id'
            )

    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_wca_completion_seated_user_missing_api_key(self):
        self.user.rh_user_has_seat = True
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            200,
            Mock(side_effect=WcaKeyNotFound),
            Mock(return_value='org-model-id'),
            DEFAULT_SUGGESTION_ID,
        )
        model_client, model_input = stub
        with patch.object(apps.get_app_config('ai'), '_wca_client', model_client):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), model_input)
                self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
                self.assertInLog("A WCA Api Key was expected but not found", log)

    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_wca_completion_seated_user_missing_model_id(self):
        self.user.rh_user_has_seat = True
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            200,
            Mock(return_value='org-api-key'),
            Mock(side_effect=WcaModelIdNotFound),
            DEFAULT_SUGGESTION_ID,
        )
        model_client, model_input = stub
        with patch.object(apps.get_app_config('ai'), '_wca_client', model_client):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), model_input)
                self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
                self.assertInLog("A WCA Model ID was expected but not found", log)

    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_wca_completion_seated_user_garbage_model_id(self):
        self.user.rh_user_has_seat = True
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            400,
            Mock(return_value='org-api-key'),
            Mock(return_value='garbage'),
            DEFAULT_SUGGESTION_ID,
        )
        model_client, model_input = stub
        with patch.object(apps.get_app_config('ai'), '_wca_client', model_client):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), model_input)
                self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
                self.assertInLog("WCA Model ID is invalid", log)

    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_wca_completion_seated_user_invalid_model_id_for_api_key(self):
        self.user.rh_user_has_seat = True
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            403,
            Mock(return_value='org-api-key'),
            Mock(return_value='org-model-id'),
            DEFAULT_SUGGESTION_ID,
        )
        model_client, model_input = stub
        with patch.object(apps.get_app_config('ai'), '_wca_client', model_client):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), model_input)
                self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
                self.assertInLog("WCA Model ID is invalid", log)

    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_wca_completion_seated_user_empty_response(self):
        self.user.rh_user_has_seat = True
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            204,
            Mock(return_value='org-api-key'),
            Mock(return_value='org-model-id'),
            DEFAULT_SUGGESTION_ID,
        )
        model_client, model_input = stub
        with patch.object(apps.get_app_config('ai'), '_wca_client', model_client):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), model_input)
                self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)
                self.assertInLog("WCA returned an empty response", log)

    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_wca_completion_seated_user_cloudflare_rejection(self):
        self.user.rh_user_has_seat = True
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            403,
            Mock(return_value='org-api-key'),
            Mock(side_effect=WcaCloudflareRejection),
            DEFAULT_SUGGESTION_ID,
        )
        model_client, model_input = stub
        with patch.object(apps.get_app_config('ai'), '_wca_client', model_client):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), model_input)
                self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
                self.assertInLog("Cloudflare rejected the request", log)

    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TIMEOUT=20)
    def test_wca_completion_timeout_single_task(self):
        self.user.rh_user_has_seat = True
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            200,
            Mock(return_value='org-api-key'),
            Mock(return_value='org-model-id'),
            DEFAULT_SUGGESTION_ID,
        )
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(DEFAULT_SUGGESTION_ID),
        }
        model_client, _ = stub
        with patch.object(apps.get_app_config('ai'), '_wca_client', model_client):
            r = self.client.post(reverse('completions'), payload)
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertEqual(model_client.session.post.call_args[1]['timeout'], 20)

    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TIMEOUT=20)
    def test_wca_completion_timeout_multi_task(self):
        self.user.rh_user_has_seat = True
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            200,
            Mock(return_value='org-api-key'),
            Mock(return_value='org-model-id'),
            DEFAULT_SUGGESTION_ID,
        )
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  "
            "tasks:\n    # Install Apache & start Apache\n",
            "suggestionId": str(DEFAULT_SUGGESTION_ID),
        }
        model_client, _ = stub
        with patch.object(apps.get_app_config('ai'), '_wca_client', model_client):
            r = self.client.post(reverse('completions'), payload)
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertEqual(model_client.session.post.call_args[1]['timeout'], 40)

    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_wca_completion_timed_out(self):
        self.user.rh_user_has_seat = True
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            200,
            Mock(return_value='org-api-key'),
            Mock(return_value='org-model-id'),
            DEFAULT_SUGGESTION_ID,
        )
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  "
            "tasks:\n    # Install Apache & start Apache\n",
            "suggestionId": str(DEFAULT_SUGGESTION_ID),
        }
        model_client, _ = stub
        model_client.session.post = Mock(side_effect=ReadTimeout())
        with patch.object(apps.get_app_config('ai'), '_wca_client', model_client):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)
                segment_events = self.extractSegmentEventsFromLog(log)
                self.assertTrue(len(segment_events) > 0)
                for event in segment_events:
                    if event['event'] == 'prediction':
                        properties = event['properties']
                        self.assertTrue(properties['exception'])
                        self.assertEqual(properties['problem'], 'ModelTimeoutError')

    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_wca_completion_request_id_correlation_failure(self):
        self.user.rh_user_has_seat = True
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            200,
            Mock(return_value='org-api-key'),
            Mock(return_value='org-model-id'),
            DEFAULT_SUGGESTION_ID,
        )
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  "
            "tasks:\n    # Install Apache & start Apache\n",
            "suggestionId": str(DEFAULT_SUGGESTION_ID),
        }
        x_request_id = uuid.uuid4()
        response = MockResponse(
            json={},
            status_code=200,
            headers={WCA_REQUEST_ID_HEADER: str(x_request_id)},
        )

        model_client, _ = stub
        model_client.session.post = Mock(return_value=response)
        with patch.object(apps.get_app_config('ai'), '_wca_client', model_client):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
                segment_events = self.extractSegmentEventsFromLog(log)
                self.assertTrue(len(segment_events) > 0)
                for event in segment_events:
                    if event['event'] == 'prediction':
                        properties = event['properties']
                        self.assertTrue(properties['exception'])
                        self.assertEqual(properties['problem'], 'WcaSuggestionIdCorrelationFailure')
                self.assertInLog(f"suggestion_id: '{DEFAULT_SUGGESTION_ID}'", log)
                self.assertInLog(f"x_request_id: '{x_request_id}'", log)


@modify_settings()
class TestCompletionView(WisdomServiceAPITestCaseBase):
    # An artificial model ID for model-ID related test cases.
    DUMMY_MODEL_ID = "01234567-1234-5678-9abc-0123456789ab<|sepofid|>wisdom_codegen"

    def test_full_payload(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": settings.ANSIBLE_AI_MODEL_NAME,
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config('ai'),
            'model_mesh_client',
            DummyMeshClient(self, payload, response_data),
        ):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data['predictions'])
                self.assertSegmentTimestamp(log)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    @patch("ai.api.pipelines.completion_stages.inference.get_model_client")
    def test_multi_task_prompt_commercial(self, mock_get_model_client):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    # Install Apache & start Apache\n",  # noqa: E501
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": settings.ANSIBLE_AI_MODEL_NAME,
            "predictions": [
                "- name:  Install Apache\n  ansible.builtin.apt:\n    name: apache2\n    state: latest\n- name:  start Apache\n  ansible.builtin.service:\n    name: apache2\n    state: started\n    enabled: yes\n"  # noqa: E501
            ],
        }
        self.user.rh_user_has_seat = True
        self.client.force_authenticate(user=self.user)
        mock_get_model_client.return_value = (
            DummyMeshClient(self, payload, response_data, rh_user_has_seat=True),
            None,
        )

        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(reverse('completions'), payload)
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertIsNotNone(r.data['predictions'])

            # confirm prediction ends with newline
            prediction = r.data['predictions'][0]
            self.assertEqual(prediction[-1], '\n')

            # confirm prediction has had whitespace lines trimmed
            self.assertEqual(prediction, trim_whitespace_lines(prediction))

            self.assertSegmentTimestamp(log)
            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            for event in segment_events:
                if event['event'] == 'completion':
                    properties = event['properties']
                    self.assertEqual(properties['taskCount'], 2)
                    self.assertEqual(properties['promptType'], CompletionsPromptType.MULTITASK)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    @patch("ai.api.pipelines.completion_stages.inference.get_model_client")
    def test_multi_task_prompt_commercial_with_pii(self, mock_get_model_client):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    #Install Apache & say hello fred@redhat.com\n",  # noqa: E501
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": settings.ANSIBLE_AI_MODEL_NAME,
            "predictions": [
                "- name:  Install Apache\n  ansible.builtin.apt:\n    name: apache2\n    state: latest\n- name:  say hello fred@redhat.com\n  ansible.builtin.debug:\n    msg: Hello there olivia1@example.com\n"  # noqa: E501
            ],
        }
        self.user.rh_user_has_seat = True
        self.client.force_authenticate(user=self.user)
        # test_inference_match=False because anonymizer changes the prompt before calling WCA
        mock_get_model_client.return_value = (
            DummyMeshClient(
                self, payload, response_data, test_inference_match=False, rh_user_has_seat=True
            ),
            None,
        )
        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(reverse('completions'), payload)
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertIsNotNone(r.data['predictions'])
            self.assertSegmentTimestamp(log)
            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            for event in segment_events:
                if event['event'] == 'completion':
                    properties = event['properties']
                    self.assertEqual(properties['taskCount'], 2)
                    self.assertEqual(properties['promptType'], CompletionsPromptType.MULTITASK)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_rate_limit(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": settings.ANSIBLE_AI_MODEL_NAME,
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config('ai'),
            'model_mesh_client',
            DummyMeshClient(self, payload, response_data),
        ):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data['predictions'])
                for _ in range(10):
                    r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.TOO_MANY_REQUESTS)
                self.assertSegmentTimestamp(log)

    def test_missing_prompt(self):
        payload = {
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": settings.ANSIBLE_AI_MODEL_NAME,
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config('ai'),
            'model_mesh_client',
            DummyMeshClient(self, payload, response_data),
        ):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
                self.assertSegmentTimestamp(log)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_authentication_error(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": settings.ANSIBLE_AI_MODEL_NAME,
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        # self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config('ai'),
            'model_mesh_client',
            DummyMeshClient(self, payload, response_data),
        ):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)
                segment_events = self.extractSegmentEventsFromLog(log)
                self.assertTrue(len(segment_events) > 0)
                for event in segment_events:
                    self.assertEqual(event['userId'], 'unknown')
                    properties = event['properties']
                    self.assertTrue('modelName' in properties)
                    self.assertTrue('imageTags' in properties)
                    self.assertEqual(properties['response']['status_code'], 401)
                    self.assertIsNotNone(event['timestamp'])

    def test_completions_preprocessing_error(self):
        payload = {
            "prompt": "---\n- hosts: all\nbecome: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": settings.ANSIBLE_AI_MODEL_NAME,
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config('ai'),
            'model_mesh_client',
            DummyMeshClient(self, payload, response_data),
        ):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
                self.assertEqual(r.data['message'], 'Request contains invalid yaml')
                self.assertSegmentTimestamp(log)

    def test_completions_preprocessing_error_with_invalid_prompt(self):
        payload = {
            "prompt": "---\n  - name: [Setup]",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": settings.ANSIBLE_AI_MODEL_NAME,
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config('ai'),
            'model_mesh_client',
            DummyMeshClient(self, payload, response_data),
        ):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
                self.assertEqual(r.data['message'], 'Request contains invalid prompt')
                self.assertSegmentTimestamp(log)

    def test_completions_preprocessing_error_without_name_prompt(self):
        payload = {
            "prompt": "---\n  - Name: [Setup]",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": settings.ANSIBLE_AI_MODEL_NAME,
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config('ai'),
            'model_mesh_client',
            DummyMeshClient(self, payload, response_data),
        ):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
                self.assertInLog("failed to validate request", log)
                self.assertTrue("prompt does not contain the name parameter" in str(r.content))
                self.assertSegmentTimestamp(log)

    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_full_payload_without_ARI(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": settings.ANSIBLE_AI_MODEL_NAME,
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config('ai'),
            'model_mesh_client',
            DummyMeshClient(self, payload, response_data),
        ):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data['predictions'])
                self.assertInLog('skipped ari post processing because ari was not initialized', log)
                self.assertSegmentTimestamp(log)

    @override_settings(ENABLE_ARI_POSTPROCESS=True)
    def test_full_payload_with_recommendation_with_broken_last_line(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        # quotation in the last line is not closed, but the truncate function can handle this.
        response_data = {
            "model_id": settings.ANSIBLE_AI_MODEL_NAME,
            "predictions": [
                "      ansible.builtin.apt:\n        name: apache2\n      register: \"test"
            ],
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
                self.assertNotInLog('the recommendation_yaml is not a valid YAML', log)
                self.assertSegmentTimestamp(log)

    @override_settings(ENABLE_ARI_POSTPROCESS=True)
    def test_completions_postprocessing_error_for_invalid_yaml(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        # this prediction has indentation problem with the prompt above
        response_data = {
            "model_id": settings.ANSIBLE_AI_MODEL_NAME,
            "predictions": ["      ansible.builtin.apt:\n garbage       name: apache2"],
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
                self.assertInLog('error postprocessing prediction for suggestion', log)
                self.assertSegmentTimestamp(log)

    @override_settings(ENABLE_ARI_POSTPROCESS=True)
    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_completions_postprocessing_for_invalid_suggestion(self):
        # the suggested task is invalid because it does not have module name
        # in this case, ARI should throw an exception
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        # module name in the prediction is ""
        response_data = {
            "model_id": settings.ANSIBLE_AI_MODEL_NAME,
            "predictions": ["      \"\":\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(
            logger='root', level='DEBUG'
        ) as log:  # Enable debug outputs for getting Segment events
            with patch.object(
                apps.get_app_config('ai'),
                'model_mesh_client',
                DummyMeshClient(self, payload, response_data),
            ):
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(HTTPStatus.NO_CONTENT, r.status_code)
                self.assertEqual(None, r.data)
                self.assertInLog('error postprocessing prediction for suggestion', log)
                segment_events = self.extractSegmentEventsFromLog(log)
                self.assertTrue(len(segment_events) > 0)
                for event in segment_events:
                    if event['event'] == 'postprocess':
                        self.assertEqual(
                            'ARI rule evaluation threw fatal exception: '
                            'Invalid task structure: no module name found',
                            event['properties']['problem'],
                        )
                    self.assertIsNotNone(event['timestamp'])

    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=True)
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_payload_with_ansible_lint(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": settings.ANSIBLE_AI_MODEL_NAME,
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='WARN'):
            with patch.object(
                apps.get_app_config('ai'),
                'model_mesh_client',
                DummyMeshClient(self, payload, response_data),
            ):
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data['predictions'])

    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=False)
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_full_payload_without_ansible_lint_without_commercial(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": settings.ANSIBLE_AI_MODEL_NAME,
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config('ai'),
            'model_mesh_client',
            DummyMeshClient(self, payload, response_data),
        ):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data['predictions'])
                self.assertInLog(
                    'skipped ansible lint post processing as lint processing is allowed'
                    ' for Commercial Users only!',
                    log,
                )
                self.assertSegmentTimestamp(log)

    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=False)
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_full_payload_without_ansible_lint_with_commercial_user(self):
        self.user.rh_user_has_seat = True
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": settings.ANSIBLE_AI_MODEL_NAME,
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config('ai'),
            '_wca_client',
            DummyMeshClient(self, payload, response_data, rh_user_has_seat=True),
        ):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data['predictions'])
                self.assertSegmentTimestamp(log)

    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=True)
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_full_payload_with_ansible_lint_with_commercial_user(self):
        self.user.rh_user_has_seat = True
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": self.DUMMY_MODEL_ID,
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config('ai'),
            '_wca_client',
            DummyMeshClient(self, payload, response_data, rh_user_has_seat=True),
        ):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data['predictions'])
                self.assertSegmentTimestamp(log)

                segment_events = self.extractSegmentEventsFromLog(log)
                self.assertTrue(len(segment_events) > 0)
                for event in segment_events:
                    properties = event['properties']
                    self.assertTrue('modelName' in properties)
                    self.assertEqual(properties['modelName'], self.DUMMY_MODEL_ID)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    @patch('ai.api.model_client.wca_client.WCAClient.infer')
    def test_wca_client_errors(self, infer):
        """Run WCA client error scenarios for various errors."""
        for error, status_code_expected in [
            (ModelTimeoutError(), HTTPStatus.NO_CONTENT),
            (WcaBadRequest(), HTTPStatus.BAD_REQUEST),
            (WcaInvalidModelId(), HTTPStatus.FORBIDDEN),
            (WcaKeyNotFound(), HTTPStatus.FORBIDDEN),
            (WcaModelIdNotFound(), HTTPStatus.FORBIDDEN),
            (WcaEmptyResponse(), HTTPStatus.NO_CONTENT),
            (ConnectionError(), HTTPStatus.SERVICE_UNAVAILABLE),
        ]:
            infer.side_effect = self.get_side_effect(error)
            self.run_wca_client_error_case(status_code_expected)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    @patch('ai.api.model_client.wca_client.WCAClient.infer')
    def test_wca_client_postprocess_error(self, infer):
        infer.return_value = {"predictions": [""], "model_id": self.DUMMY_MODEL_ID}
        self.run_wca_client_error_case(HTTPStatus.NO_CONTENT)

    def run_wca_client_error_case(self, status_code_expected):
        """Execute a single WCA client error scenario."""
        self.user.rh_user_has_seat = True
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config('ai'), '_wca_client', WCAClient(inference_url='https://wca_api_url')
        ):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, status_code_expected)
                self.assertSegmentTimestamp(log)

                segment_events = self.extractSegmentEventsFromLog(log)
                self.assertTrue(len(segment_events) > 0)
                for event in segment_events:
                    properties = event['properties']
                    self.assertTrue('modelName' in properties)
                    # Make sure the model name stored in Segment events is the one in the exception
                    # thrown from the backend server.
                    self.assertEqual(properties['modelName'], self.DUMMY_MODEL_ID)

    def get_side_effect(self, error):
        """Create a side effect for WCA error test cases."""
        # if the error is either WcaException or ModelTimeoutError,
        # assume model_id is found in the model_id property.
        if isinstance(error, (WcaException, ModelTimeoutError)):
            error.model_id = self.DUMMY_MODEL_ID
        # otherwise, assume it is a requests.exceptions.RequestException
        # found in the communication w/ WCA server.
        else:
            request = requests.PreparedRequest()
            body = {
                "model_id": self.DUMMY_MODEL_ID,
                "prompt": "---\n- hosts: all\n  become: yes\n\n"
                "  tasks:\n    - name: Install Apache\n",
            }
            request.body = json.dumps(body).encode("utf-8")
            error.request = request
        return error

    def test_completions_pii_clean_up(self):
        payload = {
            "prompt": "- name: Create an account for foo@ansible.com \n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": settings.ANSIBLE_AI_MODEL_NAME,
            "predictions": [""],
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='DEBUG') as log:
            with patch.object(
                apps.get_app_config('ai'),
                'model_mesh_client',
                DummyMeshClient(self, payload, response_data, False),
            ):
                self.client.post(reverse('completions'), payload)
                self.assertInLog('Create an account for james8@example.com', log)
                self.assertSegmentTimestamp(log)

    def test_full_completion_post_response(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": settings.ANSIBLE_AI_MODEL_NAME,
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config('ai'),
            'model_mesh_client',
            DummyMeshClient(self, payload, response_data),
        ):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data['predictions'])
                self.assertIsNotNone(r.data['model'])
                self.assertIsNotNone(r.data['suggestionId'])
                self.assertSegmentTimestamp(log)


@modify_settings()
@override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
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
            "sentimentFeedback": {
                "value": 4,
                "feedback": "This is a test feedback",
            },
            "suggestionQualityFeedback": {
                "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n"
                " - name: Install Apache\n",
                "providedSuggestion": "    when: ansible_os_family == 'Debian'\n    "
                "ansible.builtin.package:\n      name: apache2\n"
                "      state: present",
                "expectedSuggestion": "    when: ansible_os_family == 'Debian'\n    "
                "ansible.builtin.package:\n      name: apache\n"
                "      state: present",
                "additionalComment": "Package name is changed",
            },
            "issueFeedback": {
                "type": "bug-report",
                "title": "This is a test issue",
                "description": "This is a test issue description",
            },
        }
        with self.assertLogs(logger='root', level='DEBUG') as log:
            self.client.force_authenticate(user=self.user)
            r = self.client.post(reverse('feedback'), payload, format='json')
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertSegmentTimestamp(log)

    def test_missing_content(self):
        payload = {
            "ansibleContent": {"documentUri": "file:///home/user/ansible.yaml", "trigger": "0"}
        }
        with self.assertLogs(logger='root', level='DEBUG') as log:
            self.client.force_authenticate(user=self.user)
            r = self.client.post(reverse('feedback'), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assertSegmentTimestamp(log)

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
            self.client.post(reverse('feedback'), payload, format="json")
            self.assertNotInLog('file:///home/user/ansible.yaml', log)
            self.assertInLog('file:///home/ano-user/ansible.yaml', log)
            self.assertSegmentTimestamp(log)

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
        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(reverse('feedback'), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)
            self.assertSegmentTimestamp(log)

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

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            hostname = platform.node()
            for event in segment_events:
                properties = event['properties']
                self.assertTrue('modelName' in properties)
                self.assertTrue('imageTags' in properties)
                self.assertTrue('groups' in properties)
                self.assertTrue('Group 1' in properties['groups'])
                self.assertTrue('Group 2' in properties['groups'])
                self.assertTrue('rh_user_has_seat' in properties)
                self.assertTrue('rh_user_org_id' in properties)
                self.assertEqual(hostname, properties['hostname'])
                self.assertIsNotNone(event['timestamp'])

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

            segment_events = self.extractSegmentEventsFromLog(log)
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
                self.assertIsNotNone(event['timestamp'])

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

            segment_events = self.extractSegmentEventsFromLog(log)
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
                self.assertIsNotNone(event['timestamp'])

    @patch('ai.api.serializers.FeedbackRequestSerializer.is_valid')
    def test_feedback_segment_ansible_content_500_error(self, is_valid):
        is_valid.side_effect = Exception('Dummy Exception')
        payload = {
            "ansibleContent": {
                "content": "---\n- hosts: all\n  become: yes\n\n  "
                "tasks:\n    - name: Install Apache\n",
                "documentUri": "file:///home/rbobbitt/ansible.yaml",
                "activityId": str(uuid.uuid4()),
                "trigger": "0",
            }
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(reverse('feedback'), payload, format='json')
            self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
            self.assertInLog("An exception <class 'Exception'> occurred in sending a feedback", log)
            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            for event in segment_events:
                self.assertTrue('ansibleContentFeedback', event['event'])
                properties = event['properties']
                self.assertTrue('data' in properties)
                self.assertTrue('exception' in properties)
                self.assertEqual('Dummy Exception', properties['exception'])
                self.assertEqual(
                    "file:///home/ano-user/ansible.yaml",
                    properties['data']['ansibleContent']['documentUri'],
                )
                self.assertIsNotNone(event['timestamp'])

    def test_feedback_segment_suggestion_quality_feedback_error(self):
        payload = {
            "suggestionQualityFeedback": {
                # required key "prompt" is missing
                "providedSuggestion": "    when: ansible_os_family == 'Debian'\n    "
                "ansible.builtin.package:\n      name: apache2\n      "
                "state: present",
                "expectedSuggestion": "    when: ansible_os_family == 'Debian'\n    "
                "ansible.builtin.package:\n      name: apache\n      "
                "state: present",
                "additionalComment": "Package name is changed",
            }
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(reverse('feedback'), payload, format='json')
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            for event in segment_events:
                self.assertTrue('suggestionQualityFeedback', event['event'])
                properties = event['properties']
                self.assertTrue('data' in properties)
                self.assertTrue('exception' in properties)
                self.assertEqual(
                    "Package name is changed",
                    properties['data']['suggestionQualityFeedback']['additionalComment'],
                )
                self.assertIsNotNone(event['timestamp'])

    def test_feedback_segment_sentiment_feedback_error(self):
        payload = {
            "sentimentFeedback": {
                # missing required key "value"
                "feedback": "This is a test feedback",
            }
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(reverse('feedback'), payload, format='json')
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            for event in segment_events:
                self.assertTrue('suggestionQualityFeedback', event['event'])
                properties = event['properties']
                self.assertTrue('data' in properties)
                self.assertTrue('exception' in properties)
                self.assertEqual(
                    "This is a test feedback",
                    properties['data']['sentimentFeedback']['feedback'],
                )
                self.assertIsNotNone(event['timestamp'])

    def test_feedback_segment_issue_feedback_error(self):
        payload = {
            "issueFeedback": {
                "type": "bug-report",
                # missing required key "title"
                "description": "This is a test description",
            }
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(reverse('feedback'), payload, format='json')
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            for event in segment_events:
                self.assertTrue('issueFeedback', event['event'])
                properties = event['properties']
                self.assertTrue('data' in properties)
                self.assertTrue('exception' in properties)
                self.assertEqual(
                    "This is a test description",
                    properties['data']['issueFeedback']['description'],
                )
                self.assertIsNotNone(event['timestamp'])


@patch('ai.search.search')
@override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
class TestAttributionsView(WisdomServiceAPITestCaseBase):
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

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            hostname = platform.node()
            for event in segment_events:
                properties = event['properties']
                self.assertTrue('modelName' in properties)
                self.assertTrue('imageTags' in properties)
                self.assertTrue('groups' in properties)
                self.assertTrue('Group 1' in properties['groups'])
                self.assertTrue('Group 2' in properties['groups'])
                self.assertTrue('rh_user_has_seat' in properties)
                self.assertTrue('rh_user_org_id' in properties)
                self.assertEqual(hostname, properties['hostname'])
                self.assertIsNotNone(event['timestamp'])

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

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertEqual(len(segment_events), 0)
            self.assertInLog('Failed to search for attributions', log)


@modify_settings()
class TestContentMatchesWCAView(WisdomServiceAPITestCaseBase):
    @patch('ai.search.search')
    def test_wca_contentmatch_with_no_seated_user(self, mock_search):
        self.user.rh_user_has_seat = False

        repo_name = "robertdebock.nginx"
        repo_url = "https://galaxy.ansible.com/robertdebock/nginx"
        path = "tasks/main.yml"
        license = "apache-2.0"

        mock_search.return_value = {
            'attributions': [
                {
                    'repo_name': repo_name,
                    'repo_url': repo_url,
                    'path': path,
                    'license': license,
                    'data_source': DataSource.GALAXY_R,
                    'ansible_type': AnsibleType.UNKNOWN,
                    'score': 0.0,
                },
            ],
            'meta': {
                'encode_duration': 1000,
                'search_duration': 2000,
            },
        }

        self.client.force_authenticate(user=self.user)
        payload = {
            "suggestions": [
                "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n"
            ],
            "suggestionId": str(uuid.uuid4()),
        }

        r = self.client.post(reverse('contentmatches'), payload)
        self.assertEqual(r.status_code, HTTPStatus.OK)

        content_match = r.data["contentmatches"][0]["contentmatch"][0]

        self.assertEqual(content_match["repo_name"], repo_name)
        self.assertEqual(content_match["repo_url"], repo_url)
        self.assertEqual(content_match["path"], path)
        self.assertEqual(content_match["license"], license)
        self.assertEqual(content_match["data_source_description"], "Ansible Galaxy roles")

    @patch('ai.search.search')
    def test_wca_contentmatch_with_unseated_user_verify_single_task(self, mock_search):
        self.user.rh_user_has_seat = False
        self.client.force_authenticate(user=self.user)

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
            "suggestions": [
                "\n- name: install nginx on RHEL\n",
                "\n- name: Copy Fathom config into place.\n",
            ],
            "suggestionId": str(uuid.uuid4()),
        }

        r = self.client.post(reverse('contentmatches'), payload)
        self.assertEqual(r.status_code, HTTPStatus.OK)

        mock_search.assert_called_with(payload["suggestions"][0], None)

    def test_wca_contentmatch_with_seated_user_single_task(self):
        self.user.rh_user_has_seat = True
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)
        payload = {
            "suggestions": [
                "\n - name: install nginx on RHEL\n become: true\n "
                "ansible.builtin.package:\n name: nginx\n state: present\n"
            ],
            "suggestionId": str(uuid.uuid4()),
        }

        repo_name = "robertdebock.nginx"
        repo_url = "https://galaxy.ansible.com/robertdebock/nginx"
        path = "tasks/main.yml"
        license = "apache-2.0"
        data_source_description = "Ansible Galaxy roles"

        response = MockResponse(
            json=[
                {
                    "code_matches": [
                        {
                            "repo_name": repo_name,
                            "repo_url": repo_url,
                            "path": path,
                            "license": license,
                            "data_source_description": data_source_description,
                            "score": 0.94550663,
                        },
                        {
                            "repo_name": f"{repo_name}2",
                            "repo_url": f"{repo_url}2",
                            "path": path,
                            "license": license,
                            "data_source_description": data_source_description,
                            "score": 0.94550662,
                        },
                        {
                            "repo_name": f"{repo_name}3",
                            "repo_url": f"{repo_url}3",
                            "path": path,
                            "license": license,
                            "data_source_description": data_source_description,
                            "score": 0.94550661,
                        },
                        {
                            "repo_name": f"{repo_name}4",
                            "repo_url": f"{repo_url}4",
                            "path": path,
                            "license": license,
                            "data_source_description": data_source_description,
                            "score": 0.94550660,
                        },
                    ],
                    "meta": {"encode_duration": 367.3, "search_duration": 151.98},
                }
            ],
            status_code=200,
        )
        model_client = WCAClient(inference_url='https://wca_api_url')
        model_client.session.post = Mock(return_value=response)
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        model_client.get_api_key = Mock(return_value='org-api-key')
        model_client.get_model_id = Mock(return_value='org-model-id')
        with patch.object(apps.get_app_config('ai'), '_wca_client', model_client):
            r = self.client.post(reverse('contentmatches'), payload)
            self.assertEqual(r.status_code, HTTPStatus.OK)
            model_client.get_token.assert_called_once()
            self.assertEqual(
                model_client.session.post.call_args.args[0],
                "https://wca_api_url/v1/wca/codematch/ansible",
            )
            self.assertEqual(
                model_client.session.post.call_args.kwargs['json']['model_id'], 'org-model-id'
            )

            self.assertEqual(len(r.data["contentmatches"][0]["contentmatch"]), 3)

            content_match = r.data["contentmatches"][0]["contentmatch"][0]

            self.assertEqual(content_match["repo_name"], repo_name)
            self.assertEqual(content_match["repo_url"], repo_url)
            self.assertEqual(content_match["path"], path)
            self.assertEqual(content_match["license"], license)
            self.assertEqual(content_match["data_source_description"], data_source_description)

    def test_wca_contentmatch_with_seated_user_multi_task(self):
        self.user.rh_user_has_seat = True
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)
        payload = {
            "suggestions": [
                "\n- name: install nginx on RHEL\n",
                "\n- name: Copy Fathom config into place.\n",
            ],
            "suggestionId": str(uuid.uuid4()),
        }

        repo_name = "adfinis-sygroup.nginx"
        repo_url = "https://galaxy.ansible.com/davidalger/nginx"
        path = "tasks/main.yml"
        license = "mit"
        data_source_description = "Ansible Galaxy roles"

        repo_name2 = "fiaasco.solr"
        repo_url2 = "https://galaxy.ansible.com/fiaasco/solr"
        path2 = "tasks/cores.yml"
        license2 = "mit"
        data_source_description2 = "Ansible Galaxy roles"

        response = MockResponse(
            json=[
                {
                    "code_matches": [
                        {
                            "repo_name": "davidalger.nginx",
                            "repo_url": "https://galaxy.ansible.com/davidalger/nginx",
                            "path": "tasks/main.yml",
                            "license": "mit",
                            "data_source_description": "Ansible Galaxy roles",
                            "score": 0.83672893,
                        },
                        {
                            "repo_name": repo_name,
                            "repo_url": repo_url,
                            "path": path,
                            "license": license,
                            "data_source_description": data_source_description,
                            "score": 0.8233435,
                        },
                    ],
                    "meta": {"encode_duration": 135.66, "search_duration": 145.81},
                },
                {
                    "code_matches": [
                        {
                            "repo_name": repo_name2,
                            "repo_url": repo_url2,
                            "path": path2,
                            "license": license2,
                            "data_source_description": data_source_description2,
                            "score": 0.7182885,
                        }
                    ],
                    "meta": {"encode_duration": 183.02, "search_duration": 31.97},
                },
            ],
            status_code=200,
        )
        model_client = WCAClient(inference_url='https://wca_api_url')
        model_client.session.post = Mock(return_value=response)
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        model_client.get_api_key = Mock(return_value='org-api-key')
        model_client.get_model_id = Mock(return_value='org-model-id')
        with patch.object(apps.get_app_config('ai'), '_wca_client', model_client):
            r = self.client.post(reverse('contentmatches'), payload)
            self.assertEqual(r.status_code, HTTPStatus.OK)
            model_client.get_token.assert_called_once()
            self.assertEqual(
                model_client.session.post.call_args.args[0],
                "https://wca_api_url/v1/wca/codematch/ansible",
            )
            self.assertEqual(
                model_client.session.post.call_args.kwargs['json']['model_id'], 'org-model-id'
            )

            content_match = r.data["contentmatches"][0]["contentmatch"][1]
            content_match2 = r.data["contentmatches"][1]["contentmatch"][0]

            self.assertEqual(content_match["repo_name"], repo_name)
            self.assertEqual(content_match["repo_url"], repo_url)
            self.assertEqual(content_match["path"], path)
            self.assertEqual(content_match["license"], license)
            self.assertEqual(content_match["data_source_description"], data_source_description)

            self.assertEqual(content_match2["repo_name"], repo_name2)
            self.assertEqual(content_match2["repo_url"], repo_url2)
            self.assertEqual(content_match2["path"], path2)
            self.assertEqual(content_match2["license"], license2)
            self.assertEqual(content_match2["data_source_description"], data_source_description2)

    def test_wca_contentmatch_with_seated_user_with_custom_model_id(self):
        self.user.rh_user_has_seat = True
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)
        payload = {
            "suggestions": [
                "\n - name: install nginx on RHEL\n become: true\n "
                "ansible.builtin.package:\n name: nginx\n state: present\n"
            ],
            "suggestionId": str(uuid.uuid4()),
            "model": "org-model-id",
        }

        repo_name = "robertdebock.nginx"
        repo_url = "https://galaxy.ansible.com/robertdebock/nginx"
        path = "tasks/main.yml"
        license = "apache-2.0"

        response = MockResponse(
            json=[
                {
                    "code_matches": [
                        {
                            "repo_name": repo_name,
                            "repo_url": repo_url,
                            "path": path,
                            "license": license,
                            "data_source_description": "Galaxy-R",
                            "score": 0.94550663,
                        }
                    ],
                    "meta": {"encode_duration": 367.3, "search_duration": 151.98},
                }
            ],
            status_code=200,
        )
        model_client = WCAClient(inference_url='https://wca_api_url')
        model_client.session.post = Mock(return_value=response)
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        model_client.get_api_key = Mock(return_value='org-api-key')
        with patch.object(apps.get_app_config('ai'), '_wca_client', model_client):
            r = self.client.post(reverse('contentmatches'), payload)
            self.assertEqual(r.status_code, HTTPStatus.OK)
            model_client.get_token.assert_called_once()
            self.assertEqual(
                model_client.session.post.call_args.args[0],
                "https://wca_api_url/v1/wca/codematch/ansible",
            )
            self.assertEqual(
                model_client.session.post.call_args.kwargs['json']['model_id'], 'org-model-id'
            )

    def test_wca_contentmatch_with_seated_user_without_custom_model_id(self):
        self.user.rh_user_has_seat = True
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)
        payload = {
            "suggestions": [
                "\n - name: install nginx on RHEL\n become: true\n "
                "ansible.builtin.package:\n name: nginx\n state: present\n"
            ],
            "suggestionId": str(uuid.uuid4()),
        }

        repo_name = "robertdebock.nginx"
        repo_url = "https://galaxy.ansible.com/robertdebock/nginx"
        path = "tasks/main.yml"
        license = "apache-2.0"

        response = MockResponse(
            json=[
                {
                    "code_matches": [
                        {
                            "repo_name": repo_name,
                            "repo_url": repo_url,
                            "path": path,
                            "license": license,
                            "data_source_description": "Galaxy-R",
                            "score": 0.94550663,
                        }
                    ],
                    "meta": {"encode_duration": 367.3, "search_duration": 151.98},
                }
            ],
            status_code=200,
        )
        model_client = WCAClient(inference_url='https://wca_api_url')
        model_client.session.post = Mock(return_value=response)
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        model_client.get_api_key = Mock(return_value='org-api-key')
        model_client.get_model_id = Mock(return_value='org-model-id')
        with patch.object(apps.get_app_config('ai'), '_wca_client', model_client):
            r = self.client.post(reverse('contentmatches'), payload)
            self.assertEqual(r.status_code, HTTPStatus.OK)
            model_client.get_token.assert_called_once()
            self.assertEqual(
                model_client.session.post.call_args.args[0],
                "https://wca_api_url/v1/wca/codematch/ansible",
            )
            self.assertEqual(
                model_client.session.post.call_args.kwargs['json']['model_id'], 'org-model-id'
            )


class TestContentMatchesWCAViewErrors(WisdomServiceAPITestCaseBase, WisdomLogAwareMixin):
    def setUp(self):
        super().setUp()

        self.user.rh_user_has_seat = True
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)

        self.payload = {
            "suggestions": [
                "\n - name: install nginx on RHEL\n become: true\n "
                "ansible.builtin.package:\n name: nginx\n state: present\n"
            ],
            "suggestionId": str(uuid.uuid4()),
            "model": "model-id",
        }

        repo_name = "robertdebock.nginx"
        repo_url = "https://galaxy.ansible.com/robertdebock/nginx"
        path = "tasks/main.yml"
        license = "apache-2.0"

        response = MockResponse(
            json=[
                {
                    "code_matches": [
                        {
                            "repo_name": repo_name,
                            "repo_url": repo_url,
                            "path": path,
                            "license": license,
                            "data_source_description": "Galaxy-R",
                            "score": 0.94550663,
                        }
                    ],
                    "meta": {"encode_duration": 367.3, "search_duration": 151.98},
                }
            ],
            status_code=200,
        )
        self.model_client = WCAClient(inference_url='https://wca_api_url')
        self.model_client.session.post = Mock(return_value=response)
        self.model_client.get_token = Mock(return_value={"access_token": "abc"})
        self.model_client.get_api_key = Mock(return_value='org-api-key')

    def test_wca_contentmatch_with_non_existing_wca_key(self):
        self.model_client.get_api_key = Mock(side_effect=WcaKeyNotFound)
        self.model_client.get_model_id = Mock(return_value='model-id')
        self._assert_exception_in_log_and_status_code(
            "ai.api.pipelines.common.WcaKeyNotFoundException", HTTPStatus.FORBIDDEN
        )

    def test_wca_contentmatch_with_empty_response(self):
        response = MockResponse(
            json=[],
            status_code=HTTPStatus.NO_CONTENT,
        )
        self.model_client.session.post = Mock(return_value=response)
        self._assert_exception_in_log_and_status_code(
            "ai.api.pipelines.common.WcaEmptyResponseException", HTTPStatus.NO_CONTENT
        )

    def test_wca_contentmatch_with_non_existing_model_id(self):
        self.model_client.get_model_id = Mock(side_effect=WcaModelIdNotFound)
        self._assert_exception_in_log_and_status_code(
            "ai.api.pipelines.common.WcaModelIdNotFoundException", HTTPStatus.FORBIDDEN
        )

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_wca_contentmatch_with_invalid_model_id(self):
        response = MockResponse(
            json=[],
            status_code=HTTPStatus.BAD_REQUEST,
        )
        self.model_client.session.post = Mock(return_value=response)
        self._assert_exception_in_log_and_status_code(
            "ai.api.pipelines.common.WcaInvalidModelIdException", HTTPStatus.FORBIDDEN
        )
        self._assert_model_id_in_exception(self.payload["model"])

    def test_wca_contentmatch_with_bad_request(self):
        self.model_client.get_model_id = Mock(side_effect=WcaBadRequest)
        self._assert_exception_in_log_and_status_code(
            "ai.api.pipelines.common.WcaBadRequestException", HTTPStatus.BAD_REQUEST
        )

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_wca_contentmatch_cloudflare_rejection(self):
        response = MockResponse(
            json=[],
            text="cloudflare rejection",
            status_code=HTTPStatus.FORBIDDEN,
        )
        self.model_client.session.post = Mock(return_value=response)
        self._assert_exception_in_log_and_status_code(
            "ai.api.pipelines.common.WcaCloudflareRejectionException", HTTPStatus.BAD_REQUEST
        )
        self._assert_model_id_in_exception(self.payload["model"])

    def test_wca_contentmatch_with_model_timeout(self):
        self.model_client.get_model_id = Mock(side_effect=ModelTimeoutError)
        self._assert_exception_in_log_and_status_code(
            "ai.api.pipelines.common.ModelTimeoutException", HTTPStatus.NO_CONTENT
        )

    def test_wca_contentmatch_with_connection_error(self):
        self.model_client.get_model_id = Mock(side_effect=ConnectionError)
        self._assert_exception_in_log_and_status_code(
            "ai.api.pipelines.common.ServiceUnavailable", HTTPStatus.SERVICE_UNAVAILABLE
        )

    def _assert_exception_in_log_and_status_code(self, exception_name, status_code_expected):
        with self.assertLogs(logger='root', level='ERROR') as log:
            with patch.object(apps.get_app_config('ai'), '_wca_client', self.model_client):
                r = self.client.post(reverse('contentmatches'), self.payload)
                self.assertEqual(r.status_code, status_code_expected)
            self.assertInLog(exception_name, log)

    def _assert_model_id_in_exception(self, expected_model_id):
        with patch.object(apps.get_app_config('ai'), '_wca_client', self.model_client):
            r = self.client.post(reverse('contentmatches'), self.payload)
            self.assertEqual(r.data["model"], expected_model_id)


class TestContentMatchesWCAViewSegmentEvents(WisdomServiceAPITestCaseBase):
    def setUp(self):
        super().setUp()

        self.user.rh_user_has_seat = True
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)

        self.payload = {
            "suggestions": [
                "\n - name: install nginx on RHEL\n become: true\n "
                "ansible.builtin.package:\n name: nginx\n state: present\n"
            ],
            "suggestionId": str(uuid.uuid4()),
        }

        repo_name = "robertdebock.nginx"
        repo_url = "https://galaxy.ansible.com/robertdebock/nginx"
        path = "tasks/main.yml"
        license = "apache-2.0"

        wca_response = MockResponse(
            json=[
                {
                    "code_matches": [
                        {
                            "repo_name": repo_name,
                            "repo_url": repo_url,
                            "path": path,
                            "license": license,
                            "data_source_description": "Ansible Galaxy roles",
                            "score": 0.0,
                        }
                    ],
                    "meta": {"encode_duration": 1000, "search_duration": 2000},
                }
            ],
            status_code=200,
        )

        self.model_client = WCAClient(inference_url='https://wca_api_url')
        self.model_client.session.post = Mock(return_value=wca_response)
        self.model_client.get_token = Mock(return_value={"access_token": "abc"})
        self.model_client.get_api_key = Mock(return_value='org-api-key')

        self.search_response = {
            'attributions': [
                {
                    'repo_name': repo_name,
                    'repo_url': repo_url,
                    'path': path,
                    'license': license,
                    'data_source': DataSource.GALAXY_R,
                    'ansible_type': AnsibleType.UNKNOWN,
                    'score': 0.0,
                },
            ],
            'meta': {
                'encode_duration': 1000,
                'search_duration': 2000,
            },
        }

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    @patch('ai.api.views.send_segment_event')
    @patch('ai.search.search')
    def test_wca_contentmatch_segment_events_with_unseated_user(
        self, mock_search, mock_send_segment_event
    ):
        self.user.rh_user_has_seat = False

        mock_search.return_value = self.search_response

        r = self.client.post(reverse('contentmatches'), self.payload)
        self.assertEqual(r.status_code, HTTPStatus.OK)

        event = {
            'exception': False,
            'modelName': '',
            'problem': None,
            'response': {
                'contentmatches': [
                    {
                        'contentmatch': [
                            {
                                'repo_name': 'robertdebock.nginx',
                                'repo_url': 'https://galaxy.ansible.com/robertdebock/nginx',
                                'path': 'tasks/main.yml',
                                'license': 'apache-2.0',
                                'score': 0.0,
                                'data_source_description': 'Ansible Galaxy roles',
                            }
                        ]
                    }
                ]
            },
            'metadata': [{'encode_duration': 1000, 'search_duration': 2000}],
        }

        event_request = {
            'suggestions': [
                '\n - name: install nginx on RHEL\n become: true\n '
                'ansible.builtin.package:\n name: nginx\n state: present\n'
            ]
        }

        actual_event = mock_send_segment_event.call_args_list[0][0][0]

        self.assertTrue(event.items() <= actual_event.items())
        self.assertTrue(event_request.items() <= actual_event.get("request").items())

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    @patch('ai.api.views.send_segment_event')
    def test_wca_contentmatch_segment_events_with_seated_user(self, mock_send_segment_event):
        self.user.rh_user_has_seat = True
        self.model_client.get_model_id = Mock(return_value='model-id')

        with patch.object(apps.get_app_config('ai'), '_wca_client', self.model_client):
            r = self.client.post(reverse('contentmatches'), self.payload)
            self.assertEqual(r.status_code, HTTPStatus.OK)

            event = {
                'exception': False,
                'modelName': 'model-id',
                'problem': None,
                'response': {
                    'contentmatches': [
                        {
                            'contentmatch': [
                                {
                                    'repo_name': 'robertdebock.nginx',
                                    'repo_url': 'https://galaxy.ansible.com/robertdebock/nginx',
                                    'path': 'tasks/main.yml',
                                    'license': 'apache-2.0',
                                    'score': 0.0,
                                    'data_source_description': 'Ansible Galaxy roles',
                                }
                            ]
                        }
                    ]
                },
                'metadata': [{'encode_duration': 1000, 'search_duration': 2000}],
                'rh_user_has_seat': True,
                'rh_user_org_id': '1',
            }

            event_request = {
                'suggestions': [
                    '\n - name: install nginx on RHEL\n become: true\n '
                    'ansible.builtin.package:\n name: nginx\n state: present\n'
                ]
            }

            actual_event = mock_send_segment_event.call_args_list[0][0][0]

            self.assertTrue(event.items() <= actual_event.items())
            self.assertTrue(event_request.items() <= actual_event.get("request").items())

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    @patch('ai.api.views.send_segment_event')
    def test_wca_contentmatch_segment_events_with_invalid_modelid_error(
        self, mock_send_segment_event
    ):
        self.user.rh_user_has_seat = True
        self.payload["model"] = 'invalid-model-id'
        response = MockResponse(
            json=[],
            status_code=HTTPStatus.BAD_REQUEST,
        )
        self.model_client.session.post = Mock(return_value=response)

        with patch.object(apps.get_app_config('ai'), '_wca_client', self.model_client):
            r = self.client.post(reverse('contentmatches'), self.payload)
            self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)

            event = {
                'exception': True,
                'modelName': 'invalid-model-id',
                'problem': 'WcaInvalidModelId',
                'response': {},
                'metadata': [],
                'rh_user_has_seat': True,
                'rh_user_org_id': '1',
            }

            event_request = {
                'suggestions': [
                    '\n - name: install nginx on RHEL\n become: true\n '
                    'ansible.builtin.package:\n name: nginx\n state: present\n'
                ]
            }

            actual_event = mock_send_segment_event.call_args_list[0][0][0]

            self.assertTrue(event.items() <= actual_event.items())
            self.assertTrue(event_request.items() <= actual_event.get("request").items())

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    @patch('ai.api.views.send_segment_event')
    def test_wca_contentmatch_segment_events_with_empty_response_error(
        self, mock_send_segment_event
    ):
        self.user.rh_user_has_seat = True
        self.model_client.get_model_id = Mock(return_value='model-id')

        response = MockResponse(
            json=[],
            status_code=HTTPStatus.NO_CONTENT,
        )
        self.model_client.session.post = Mock(return_value=response)

        with patch.object(apps.get_app_config('ai'), '_wca_client', self.model_client):
            r = self.client.post(reverse('contentmatches'), self.payload)
            self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)

            event = {
                'exception': True,
                'modelName': 'model-id',
                'problem': 'WcaEmptyResponse',
                'response': {},
                'metadata': [],
                'rh_user_has_seat': True,
                'rh_user_org_id': '1',
            }

            event_request = {
                'suggestions': [
                    '\n - name: install nginx on RHEL\n become: true\n '
                    'ansible.builtin.package:\n name: nginx\n state: present\n'
                ]
            }

            actual_event = mock_send_segment_event.call_args_list[0][0][0]

            self.assertTrue(event.items() <= actual_event.items())
            self.assertTrue(event_request.items() <= actual_event.get("request").items())

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    @patch('ai.api.views.send_segment_event')
    def test_wca_contentmatch_segment_events_with_key_error(self, mock_send_segment_event):
        self.user.rh_user_has_seat = True
        self.model_client.get_api_key = Mock(side_effect=WcaKeyNotFound)
        self.model_client.get_model_id = Mock(return_value='model-id')

        with patch.object(apps.get_app_config('ai'), '_wca_client', self.model_client):
            r = self.client.post(reverse('contentmatches'), self.payload)
            self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)

            event = {
                'exception': True,
                'modelName': '',
                'problem': 'WcaKeyNotFound',
                'response': {},
                'metadata': [],
                'rh_user_has_seat': True,
                'rh_user_org_id': '1',
            }

            event_request = {
                'suggestions': [
                    '\n - name: install nginx on RHEL\n become: true\n '
                    'ansible.builtin.package:\n name: nginx\n state: present\n'
                ]
            }

            actual_event = mock_send_segment_event.call_args_list[0][0][0]

            self.assertTrue(event.items() <= actual_event.items())
            self.assertTrue(event_request.items() <= actual_event.get("request").items())
