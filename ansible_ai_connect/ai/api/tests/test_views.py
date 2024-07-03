#!/usr/bin/env python3

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
import json
import logging
import platform
import random
import string
import time
import uuid
from http import HTTPStatus
from typing import Any, Dict, Optional, Union
from unittest import skip
from unittest.mock import ANY, Mock, patch

import requests
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import modify_settings, override_settings
from django.urls import reverse
from django.utils import timezone
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.runnables.utils import Input, Output
from requests.exceptions import ReadTimeout
from rest_framework.exceptions import APIException
from rest_framework.test import APITransactionTestCase
from segment import analytics

import ansible_ai_connect.ai.api.utils.segment
from ansible_ai_connect.ai.api.data.data_model import APIPayload
from ansible_ai_connect.ai.api.exceptions import (  # FeedbackValidationException,
    ModelTimeoutException,
    PostprocessException,
    PreprocessInvalidYamlException,
    ServiceUnavailable,
    WcaBadRequestException,
    WcaCloudflareRejectionException,
    WcaEmptyResponseException,
    WcaInvalidModelIdException,
    WcaKeyNotFoundException,
    WcaModelIdNotFoundException,
    WcaNoDefaultModelIdException,
    WcaSuggestionIdCorrelationFailureException,
    WcaUserTrialExpiredException,
)
from ansible_ai_connect.ai.api.model_client.base import ModelMeshClient
from ansible_ai_connect.ai.api.model_client.exceptions import (
    ModelTimeoutError,
    WcaBadRequest,
    WcaEmptyResponse,
    WcaException,
    WcaInvalidModelId,
    WcaKeyNotFound,
    WcaModelIdNotFound,
    WcaNoDefaultModelId,
    WcaUserTrialExpired,
)
from ansible_ai_connect.ai.api.model_client.tests.test_wca_client import (
    WCA_REQUEST_ID_HEADER,
    MockResponse,
)
from ansible_ai_connect.ai.api.model_client.wca_client import WCAClient
from ansible_ai_connect.ai.api.pipelines.completion_context import CompletionContext
from ansible_ai_connect.ai.api.pipelines.completion_stages.post_process import (
    trim_whitespace_lines,
)
from ansible_ai_connect.ai.api.pipelines.completion_stages.pre_process import (
    completion_pre_process,
)
from ansible_ai_connect.ai.api.pipelines.completion_stages.response import (
    CompletionsPromptType,
)
from ansible_ai_connect.ai.api.serializers import CompletionRequestSerializer
from ansible_ai_connect.ai.api.utils import segment_analytics_telemetry
from ansible_ai_connect.main.tests.test_views import create_user_with_provider
from ansible_ai_connect.organizations.models import Organization
from ansible_ai_connect.test_utils import (
    WisdomAppsBackendMocking,
    WisdomLogAwareMixin,
    WisdomServiceLogAwareTestCase,
)
from ansible_ai_connect.users.constants import USER_SOCIAL_AUTH_PROVIDER_AAP

logger = logging.getLogger(__name__)

DEFAULT_SUGGESTION_ID = uuid.uuid4()


class MockedLLM(Runnable):
    def __init__(self, response_data):
        self.response_data = response_data

    def invoke(self, input: Input, config: Optional[RunnableConfig] = None) -> Output:
        return self.response_data


class MockedMeshClient(ModelMeshClient):
    def __init__(
        self,
        test,
        payload,
        response_data,
        test_inference_match=True,
        rh_user_has_seat=False,
    ):
        super().__init__(inference_url="dummy inference url")
        self.test = test
        self.test_inference_match = test_inference_match

        if "prompt" in payload:
            try:
                user = Mock(rh_user_has_seat=rh_user_has_seat)
                request = Mock(user=user)
                serializer = CompletionRequestSerializer(context={"request": request})
                data = serializer.validate(payload.copy())
                api_payload = APIPayload(prompt=data.get("prompt"), context=data.get("context"))

                context = CompletionContext(
                    request=request,
                    payload=api_payload,
                )
                completion_pre_process(context)

                self.expects = {
                    "instances": [
                        {
                            "context": context.payload.context,
                            "prompt": context.payload.prompt,
                            "suggestionId": payload.get("suggestionId"),
                        }
                    ]
                }
            except Exception:  # ignore exception thrown here
                logger.exception("MockedMeshClient: cannot set the .expects key")

        self.response_data = response_data

    def infer(self, request, model_input, model_id="", suggestion_id=None) -> Dict[str, Any]:
        if self.test_inference_match:
            self.test.assertEqual(model_input, self.expects)
        time.sleep(0.1)  # w/o this line test_rate_limit() fails...
        # i.e., still receives 200 after 10 API calls...
        return self.response_data

    def get_model_id(
        self,
        organization_id: Optional[int] = None,
        requested_model_id: str = "",
    ) -> str:
        return requested_model_id or ""

    def get_chat_model(self, model_id):
        return MockedLLM(self.response_data)

    def generate_playbook(
        self, request, text: str = "", create_outline: bool = False, outline: str = ""
    ) -> tuple[str, str]:
        return self.response_data, self.response_data

    def explain_playbook(self, request, content) -> str:
        return self.response_data


class WisdomServiceAPITestCaseBase(APITransactionTestCase, WisdomServiceLogAwareTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        analytics.send = False  # do not send data to segment from unit tests
        segment_analytics_telemetry.send = False  # do not send data to segment from unit tests

    def setUp(self):
        super().setUp()
        self.username = "u" + "".join(random.choices(string.digits, k=5))
        self.password = "secret"
        email = "user@example.com"
        self.user = get_user_model().objects.create_user(
            username=self.username,
            email=email,
            password=self.password,
        )
        self.user.user_id = str(uuid.uuid4())
        self.user.community_terms_accepted = timezone.now()
        self.user.save()

        group_1, _ = Group.objects.get_or_create(name="Group 1")
        group_2, _ = Group.objects.get_or_create(name="Group 2")
        group_1.user_set.add(self.user)
        group_2.user_set.add(self.user)
        cache.clear()

    def tearDown(self):
        Organization.objects.filter(id=1).delete()
        self.user.delete()
        super().tearDown()

    def login(self):
        self.client.login(username=self.username, password=self.password)


@override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="wca")
@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
class TestCompletionWCAView(WisdomAppsBackendMocking, WisdomServiceAPITestCaseBase):
    def stub_wca_client(
        self,
        status_code=None,
        mock_api_key=Mock(return_value="org-api-key"),
        mock_model_id=Mock(return_value="org-model-id"),
        response_data: dict = {
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"]
        },
    ):
        model_input = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(DEFAULT_SUGGESTION_ID),
        }
        response = MockResponse(
            json=response_data,
            status_code=status_code,
            headers={WCA_REQUEST_ID_HEADER: str(DEFAULT_SUGGESTION_ID)},
        )
        model_client = WCAClient(inference_url="https://wca_api_url")
        model_client.session.post = Mock(return_value=response)
        model_client.get_api_key = mock_api_key
        model_client.get_model_id = mock_model_id
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        return model_client, model_input

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_wca_completion(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            200,
        )
        model_client, model_input = stub
        self.mock_model_client_with(model_client)
        r = self.client.post(reverse("completions"), model_input)
        self.assertEqual(r.status_code, HTTPStatus.OK)
        model_client.get_token.assert_called_once()
        self.assertEqual(
            model_client.session.post.call_args.args[0],
            "https://wca_api_url/v1/wca/codegen/ansible",
        )
        self.assertEqual(
            model_client.session.post.call_args.kwargs["json"]["model_id"], "org-model-id"
        )

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    @override_settings(ENABLE_ADDITIONAL_CONTEXT=True)
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_wca_completion_anonymized_additional_context(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            200,
        )
        model_client, model_input = stub
        model_input["metadata"] = {
            "additionalContext": {
                "playbookContext": {
                    "varInfiles": {
                        "vars.yml": "external_var_1: value1\n"
                        "external_var_2: value2\n"
                        "password: magic\n"
                    },
                    "roles": {},
                    "includeVars": {},
                },
                "roleContext": {},
                "standaloneTaskContext": {},
            },
        }
        self.mock_model_client_with(model_client)
        r = self.client.post(reverse("completions"), model_input, format="json")
        self.assertEqual(r.status_code, HTTPStatus.OK)
        prompt = model_client.session.post.call_args.kwargs["json"]["prompt"]
        self.assertTrue("external_var_1: value1" in prompt)
        self.assertTrue("external_var_2: value2" in prompt)
        self.assertTrue("password:" in prompt)
        self.assertFalse("magic" in prompt)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_wca_completion_seated_user_missing_api_key(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            200,
            Mock(side_effect=WcaKeyNotFound),
        )
        model_client, model_input = stub
        self.mock_model_client_with(model_client)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("completions"), model_input)
            self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
            self.assert_error_detail(
                r, WcaKeyNotFoundException.default_code, WcaKeyNotFoundException.default_detail
            )
            self.assertInLog("A WCA Api Key was expected but not found", log)
            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            for event in segment_events:
                properties = event["properties"]
                self.assertEqual(properties["modelName"], "")
                if event["event"] == "completion":
                    self.assertEqual(properties["response"]["status_code"], 403)
                elif event["event"] == "prediction":
                    self.assertEqual(properties["problem"], "WcaKeyNotFound")

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_wca_completion_user_not_linked_to_org(self):
        self.user.rh_user_has_seat = True
        self.user.organization = None
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            200,
            mock_model_id=Mock(side_effect=WcaNoDefaultModelId),
        )
        model_client, model_input = stub
        self.mock_model_client_with(model_client)
        r = self.client.post(reverse("completions"), model_input)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("completions"), model_input)
            self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
            self.assert_error_detail(
                r,
                WcaNoDefaultModelIdException.default_code,
                WcaNoDefaultModelIdException.default_detail,
            )
            self.assertInLog("No default WCA Model ID was found for suggestion", log)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_wca_completion_seated_user_missing_model_id(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            200,
            mock_model_id=Mock(side_effect=WcaModelIdNotFound),
        )
        model_client, model_input = stub
        self.mock_model_client_with(model_client)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("completions"), model_input)
            self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
            self.assert_error_detail(
                r,
                WcaModelIdNotFoundException.default_code,
                WcaModelIdNotFoundException.default_detail,
            )
            self.assertInLog("A WCA Model ID was expected but not found", log)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_wca_completion_seated_user_garbage_model_id(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            400,
            mock_model_id=Mock(return_value="garbage"),
            response_data={"error": "Bad request: [('value_error', ('body', 'model_id'))]"},
        )
        model_client, model_input = stub
        self.mock_model_client_with(model_client)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("completions"), model_input)
            self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
            self.assert_error_detail(
                r,
                WcaInvalidModelIdException.default_code,
                WcaInvalidModelIdException.default_detail,
            )
            self.assertInLog("WCA Model ID is invalid", log)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_wca_completion_seated_user_not_quite_valid_model_id(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            400,
            mock_model_id=Mock(
                return_value="\\b8a86397-ef64-4ddb-bbf4-a2fd164577bb<|sepofid|>granite-3b"
            ),
            response_data={
                "detail": "Failed to parse space ID and model ID: Input should be a valid UUID,"
                " invalid character: expected an optional prefix of `urn:uuid:`"
                " followed by [0-9a-fA-F-], found `\\` at 1"
            },
        )
        model_client, model_input = stub
        self.mock_model_client_with(model_client)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("completions"), model_input)
            self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
            self.assert_error_detail(
                r,
                WcaInvalidModelIdException.default_code,
                WcaInvalidModelIdException.default_detail,
            )
            self.assertInLog("WCA Model ID is invalid", log)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_wca_completion_seated_user_invalid_model_id_for_api_key(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            403,
        )
        model_client, model_input = stub
        self.mock_model_client_with(model_client)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("completions"), model_input)
            self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
            self.assert_error_detail(
                r,
                WcaInvalidModelIdException.default_code,
                WcaInvalidModelIdException.default_detail,
            )
            self.assertInLog("WCA Model ID is invalid", log)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_wca_completion_seated_user_empty_response(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            204,
        )
        model_client, model_input = stub
        self.mock_model_client_with(model_client)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("completions"), model_input)
            self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)
            self.assert_error_detail(
                r,
                WcaEmptyResponseException.default_code,
                WcaEmptyResponseException.default_detail,
            )
            self.assertInLog("WCA returned an empty response", log)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_wca_completion_seated_user_cloudflare_rejection(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        model_client, model_input = self.stub_wca_client()
        response = MockResponse(
            json=[],
            text="cloudflare rejection",
            status_code=HTTPStatus.FORBIDDEN,
        )
        model_client.session.post = Mock(return_value=response)
        self.mock_model_client_with(model_client)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("completions"), model_input)
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assert_error_detail(
                r,
                WcaCloudflareRejectionException.default_code,
                WcaCloudflareRejectionException.default_detail,
            )
            self.assertInLog("Cloudflare rejected the request", log)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_wca_completion_wml_api_call_failed(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        model_client, model_input = self.stub_wca_client()
        response = MockResponse(
            json={"detail": "WML API call failed: Deployment id or name banana was not found."},
            status_code=HTTPStatus.NOT_FOUND,
            headers={"Content-Type": "application/json"},
        )
        model_client.session.post = Mock(return_value=response)
        self.mock_model_client_with(model_client)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("completions"), model_input)
            self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
            self.assert_error_detail(
                r,
                WcaInvalidModelIdException.default_code,
                WcaInvalidModelIdException.default_detail,
            )
            self.assertInLog("WCA Model ID is invalid", log)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_wca_completion_seated_user_trial_expired_rejection(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        model_client, model_input = self.stub_wca_client()
        model_client.session.post = Mock(side_effect=WcaUserTrialExpired())
        self.mock_model_client_with(model_client)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("completions"), model_input)
            self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
            self.assert_error_detail(
                r,
                WcaUserTrialExpiredException.default_code,
                WcaUserTrialExpiredException.default_detail,
            )
            self.assertInLog("User trial expired", log)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_wca_completion_seated_user_trial_expired(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            403, response_data={"message_id": "WCA-0001-E", "detail": "The CUH limit is reached."}
        )
        model_client, model_input = stub
        self.mock_model_client_with(model_client)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("completions"), model_input)
            self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
            self.assert_error_detail(
                r,
                WcaUserTrialExpiredException.default_code,
                WcaUserTrialExpiredException.default_detail,
            )
            self.assertInLog("User trial expired", log)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_wca_completion_seated_user_model_id_error(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        model_client, model_input = self.stub_wca_client()
        response = MockResponse(
            json={"error": "Bad request: [('value_error', ('body', 'model_id'))]"},
            status_code=HTTPStatus.BAD_REQUEST,
        )
        model_client.session.post = Mock(return_value=response)
        self.mock_model_client_with(model_client)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("completions"), model_input)
            self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
            self.assert_error_detail(
                r,
                WcaInvalidModelIdException.default_code,
                WcaInvalidModelIdException.default_detail,
            )
            self.assertInLog("WCA Model ID is invalid", log)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid<|sepofid|>valid")
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TIMEOUT=20)
    def test_wca_completion_timeout_single_task(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            200,
        )
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(DEFAULT_SUGGESTION_ID),
        }
        model_client, _ = stub
        self.mock_model_client_with(model_client)
        r = self.client.post(reverse("completions"), payload)
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertEqual(model_client.session.post.call_args[1]["timeout"], 20)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid<|sepofid|>valid")
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TIMEOUT=20)
    def test_wca_completion_timeout_multi_task(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            200,
            response_data={
                "predictions": [
                    "- name:  Install Apache\n  ansible.builtin.package:\n    name: apache2\n    "  # noqa: E501
                    "state: present\n- name:  start Apache\n  ansible.builtin.service:\n    name: apache2\n"  # noqa: E501
                    "    state: started\n    enabled: true\n"
                ],
            },
        )
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  "
            "tasks:\n    # Install Apache & start Apache\n",
            "suggestionId": str(DEFAULT_SUGGESTION_ID),
        }
        model_client, _ = stub
        self.mock_model_client_with(model_client)
        r = self.client.post(reverse("completions"), payload)
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertEqual(model_client.session.post.call_args[1]["timeout"], 40)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid<|sepofid|>valid")
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_wca_completion_timed_out(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            200,
        )
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  "
            "tasks:\n    # Install Apache & start Apache\n",
            "suggestionId": str(DEFAULT_SUGGESTION_ID),
        }
        model_client, _ = stub
        model_client.session.post = Mock(side_effect=ReadTimeout())
        self.mock_model_client_with(model_client)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("completions"), payload)
            self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)
            self.assert_error_detail(
                r,
                ModelTimeoutException.default_code,
                ModelTimeoutException.default_detail,
            )
            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            for event in segment_events:
                if event["event"] == "prediction":
                    properties = event["properties"]
                    self.assertTrue(properties["exception"])
                    self.assertEqual(properties["problem"], "ModelTimeoutError")

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_wca_completion_request_id_correlation_failure(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            200,
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
        self.mock_model_client_with(model_client)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("completions"), payload)
            self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
            self.assert_error_detail(
                r,
                WcaSuggestionIdCorrelationFailureException.default_code,
                WcaSuggestionIdCorrelationFailureException.default_detail,
            )
            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            for event in segment_events:
                if event["event"] == "prediction":
                    properties = event["properties"]
                    self.assertTrue(properties["exception"])
                    self.assertEqual(properties["problem"], "WcaSuggestionIdCorrelationFailure")
            self.assertInLog(f"suggestion_id: '{DEFAULT_SUGGESTION_ID}'", log)
            self.assertInLog(f"x_request_id: '{x_request_id}'", log)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    @patch("ansible_ai_connect.main.middleware.send_segment_event")
    def test_wca_completion_segment_event_with_invalid_model_id_error(
        self, mock_send_segment_event
    ):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            400,
            mock_model_id=Mock(return_value="garbage"),
            response_data={"error": "Bad request: [('value_error', ('body', 'model_id'))]"},
        )
        model_client, model_input = stub
        model_input["prompt"] = (
            "---\n- hosts: all\n  become: yes\n\n  tasks:\n    # Install Apache & start apache\n"
        )
        self.mock_model_client_with(model_client)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("completions"), model_input)
            self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
            self.assert_error_detail(
                r,
                WcaInvalidModelIdException.default_code,
                WcaInvalidModelIdException.default_detail,
            )
            self.assertInLog("WCA Model ID is invalid", log)

            actual_event = mock_send_segment_event.call_args_list[0][0][0]
            self.assertEqual(actual_event.get("promptType"), "MULTITASK")


@modify_settings()
@override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="wca")
@override_settings(ANSIBLE_AI_MODEL_NAME="my-model")
class TestCompletionView(WisdomServiceAPITestCaseBase):
    # An artificial model ID for model-ID related test cases.
    DUMMY_MODEL_ID = "01234567-1234-5678-9abc-0123456789ab<|sepofid|>wisdom_codegen"

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
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
            apps.get_app_config("ai"),
            "model_mesh_client",
            MockedMeshClient(self, payload, response_data),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data["predictions"])
                self.assertSegmentTimestamp(log)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_multi_task_prompt_commercial(self):
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
        with patch.object(
            apps.get_app_config("ai"),
            "model_mesh_client",
            MockedMeshClient(self, payload, response_data, rh_user_has_seat=True),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data["predictions"])

                # confirm prediction ends with newline
                prediction = r.data["predictions"][0]
                self.assertEqual(prediction[-1], "\n")

                # confirm prediction has had whitespace lines trimmed
                self.assertEqual(prediction, trim_whitespace_lines(prediction))

                # confirm blank line between two tasks
                self.assertTrue("\n\n    - name: Start" in prediction)

                self.assertSegmentTimestamp(log)
                segment_events = self.extractSegmentEventsFromLog(log)
                self.assertTrue(len(segment_events) > 0)
                for event in segment_events:
                    if event["event"] == "completion":
                        properties = event["properties"]
                        self.assertEqual(properties["taskCount"], 2)
                        self.assertEqual(properties["promptType"], CompletionsPromptType.MULTITASK)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_multi_task_prompt_commercial_with_pii(self):
        pii_task = "say hello fred@redhat.com"
        payload = {
            "prompt": f"---\n- hosts: all\n  become: yes\n\n  tasks:\n    #Install Apache & {pii_task}\n",  # noqa: E501
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": settings.ANSIBLE_AI_MODEL_NAME,
            "predictions": [
                "- name:  Install Apache\n  ansible.builtin.apt:\n    name: apache2\n    state: latest\n- name:  say hello test@example.com\n  ansible.builtin.debug:\n    msg: Hello there olivia1@example.com\n"  # noqa: E501
            ],
        }
        self.user.rh_user_has_seat = True
        self.client.force_authenticate(user=self.user)
        # test_inference_match=False because anonymizer changes the prompt before calling WCA
        with patch.object(
            apps.get_app_config("ai"),
            "model_mesh_client",
            MockedMeshClient(
                self, payload, response_data, test_inference_match=False, rh_user_has_seat=True
            ),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data["predictions"])
                self.assertNotIn(pii_task.capitalize(), r.data["predictions"][0])
                self.assertSegmentTimestamp(log)
                segment_events = self.extractSegmentEventsFromLog(log)
                self.assertTrue(len(segment_events) > 0)
                for event in segment_events:
                    if event["event"] == "completion":
                        properties = event["properties"]
                        self.assertEqual(properties["taskCount"], 2)
                        self.assertEqual(properties["promptType"], CompletionsPromptType.MULTITASK)

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
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
            apps.get_app_config("ai"),
            "model_mesh_client",
            MockedMeshClient(self, payload, response_data),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data["predictions"])
                for _ in range(10):
                    r = self.client.post(reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.TOO_MANY_REQUESTS)
                self.assertSegmentTimestamp(log)

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
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
            apps.get_app_config("ai"),
            "model_mesh_client",
            MockedMeshClient(self, payload, response_data),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
                self.assertSegmentTimestamp(log)

    @skip("Why do we need a Schema1 event when access is denied?")
    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
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
            apps.get_app_config("ai"),
            "model_mesh_client",
            MockedMeshClient(self, payload, response_data),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)
                segment_events = self.extractSegmentEventsFromLog(log)
                self.assertTrue(len(segment_events) > 0)
                for event in segment_events:
                    self.assertEqual(event["userId"], "unknown")
                    properties = event["properties"]
                    self.assertTrue("modelName" in properties)
                    self.assertTrue("imageTags" in properties)
                    self.assertEqual(properties["response"]["status_code"], 401)
                    self.assertIsNotNone(event["timestamp"])

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
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
            apps.get_app_config("ai"),
            "model_mesh_client",
            MockedMeshClient(self, payload, response_data),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
                self.assert_error_detail(
                    r,
                    PreprocessInvalidYamlException.default_code,
                    PreprocessInvalidYamlException.default_detail,
                )
                self.assertSegmentTimestamp(log)

    @skip("Collect invalid payload error")
    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
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
            apps.get_app_config("ai"),
            "model_mesh_client",
            MockedMeshClient(self, payload, response_data),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
                self.assertInLog("failed to validate request", log)
                self.assertTrue("prompt does not contain the name parameter" in str(r.content))
                self.assertSegmentTimestamp(log)

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
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
            apps.get_app_config("ai"),
            "model_mesh_client",
            MockedMeshClient(self, payload, response_data),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data["predictions"])
                self.assertInLog("skipped ari post processing because ari was not initialized", log)
                self.assertSegmentTimestamp(log)

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
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
                '      ansible.builtin.apt:\n        name: apache2\n      register: "test'
            ],
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger="root", level="INFO") as log:
            with patch.object(
                apps.get_app_config("ai"),
                "model_mesh_client",
                MockedMeshClient(self, payload, response_data),
            ):
                r = self.client.post(reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data["predictions"])
                self.assertNotInLog("the recommendation_yaml is not a valid YAML", log)
                self.assertSegmentTimestamp(log)

    @override_settings(ENABLE_ARI_POSTPROCESS=True)
    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
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
        with self.assertLogs(logger="root", level="ERROR") as log:  # Suppress debug output
            with patch.object(
                apps.get_app_config("ai"),
                "model_mesh_client",
                MockedMeshClient(self, payload, response_data),
            ):
                r = self.client.post(reverse("completions"), payload)
                self.assertEqual(HTTPStatus.NO_CONTENT, r.status_code)
                self.assert_error_detail(
                    r, PostprocessException.default_code, PostprocessException.default_detail
                )
                self.assertInLog("error postprocessing prediction for suggestion", log)
                self.assertSegmentTimestamp(log)

    @override_settings(ENABLE_ARI_POSTPROCESS=True)
    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
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
            "predictions": ['      "":\n        name: apache2'],
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(
            logger="root", level="DEBUG"
        ) as log:  # Enable debug outputs for getting Segment events
            with patch.object(
                apps.get_app_config("ai"),
                "model_mesh_client",
                MockedMeshClient(self, payload, response_data),
            ):
                r = self.client.post(reverse("completions"), payload)
                self.assertEqual(HTTPStatus.NO_CONTENT, r.status_code)
                self.assertIsNone(r.data)
                self.assert_error_detail(
                    r,
                    PostprocessException.default_code,
                    PostprocessException.default_detail,
                )
                self.assertInLog("error postprocessing prediction for suggestion", log)
                segment_events = self.extractSegmentEventsFromLog(log)
                self.assertTrue(len(segment_events) > 0)
                for event in segment_events:
                    if event["event"] == "postprocess":
                        self.assertEqual(
                            "ARI rule evaluation threw fatal exception: "
                            "Invalid task structure: no module name found",
                            event["properties"]["problem"],
                        )
                    self.assertIsNotNone(event["timestamp"])

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=True)
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_payload_with_ansible_lint_without_commercial(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": settings.ANSIBLE_AI_MODEL_NAME,
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger="root", level="WARN"):
            with patch.object(
                apps.get_app_config("ai"),
                "model_mesh_client",
                MockedMeshClient(self, payload, response_data),
            ):
                r = self.client.post(reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data["predictions"])

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
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
            apps.get_app_config("ai"),
            "model_mesh_client",
            MockedMeshClient(self, payload, response_data),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data["predictions"])
                self.assertInLog(
                    "skipped ansible lint post processing as lint processing is allowed"
                    " for Commercial Users only!",
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
            apps.get_app_config("ai"),
            "model_mesh_client",
            MockedMeshClient(self, payload, response_data, rh_user_has_seat=True),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data["predictions"])
                self.assertSegmentTimestamp(log)

    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=True)
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_full_payload_with_ansible_lint_without_ari_postprocess_with_commercial_user(self):
        self.user.rh_user_has_seat = True
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Sample shell\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": self.DUMMY_MODEL_ID,
            "predictions": ["      ansible.builtin.shell:\n        cmd: echo hello"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config("ai"),
            "model_mesh_client",
            MockedMeshClient(self, payload, response_data, rh_user_has_seat=True),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data["predictions"])
                self.assertEqual(
                    r.data["predictions"][0],
                    "      ansible.builtin.command:\n        cmd: echo hello\n",
                )
                self.assertSegmentTimestamp(log)

                segment_events = self.extractSegmentEventsFromLog(log)
                self.assertTrue(len(segment_events) > 0)
                for event in segment_events:
                    properties = event["properties"]
                    self.assertTrue("modelName" in properties)
                    self.assertEqual(properties["modelName"], self.DUMMY_MODEL_ID)

    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=True)
    @override_settings(ENABLE_ARI_POSTPROCESS=True)
    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_full_payload_with_ansible_lint_with_ari_postprocess_with_commercial_user(self):
        self.user.rh_user_has_seat = True
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Sample shell\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": self.DUMMY_MODEL_ID,
            "predictions": ["      ansible.builtin.shell:\n        cmd: echo hello"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config("ai"),
            "model_mesh_client",
            MockedMeshClient(self, payload, response_data, rh_user_has_seat=True),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data["predictions"])
                self.assertEqual(
                    r.data["predictions"][0],
                    "      ansible.builtin.command:\n        cmd: echo hello\n",
                )
                self.assertSegmentTimestamp(log)

                segment_events = self.extractSegmentEventsFromLog(log)
                self.assertTrue(len(segment_events) > 0)
                for event in segment_events:
                    properties = event["properties"]
                    self.assertTrue("modelName" in properties)
                    self.assertEqual(properties["modelName"], self.DUMMY_MODEL_ID)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    @patch("ansible_ai_connect.ai.api.model_client.wca_client.WCAClient.infer")
    def test_wca_client_errors(self, infer):
        """Run WCA client error scenarios for various errors."""
        for error, status_code_expected in [
            (ModelTimeoutError(), HTTPStatus.NO_CONTENT),
            (WcaBadRequest(), HTTPStatus.NO_CONTENT),
            (WcaInvalidModelId(), HTTPStatus.FORBIDDEN),
            (WcaKeyNotFound(), HTTPStatus.FORBIDDEN),
            (WcaNoDefaultModelId(), HTTPStatus.FORBIDDEN),
            (WcaModelIdNotFound(), HTTPStatus.FORBIDDEN),
            (WcaEmptyResponse(), HTTPStatus.NO_CONTENT),
        ]:
            infer.side_effect = self.get_side_effect(error)
            self.run_wca_client_error_case(status_code_expected, error)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    @patch("ansible_ai_connect.ai.api.model_client.wca_client.WCAClient.infer")
    def test_wca_client_postprocess_error(self, infer):
        infer.return_value = {"predictions": [""], "model_id": self.DUMMY_MODEL_ID}
        self.run_wca_client_error_case(HTTPStatus.NO_CONTENT, PostprocessException())

    def run_wca_client_error_case(self, status_code_expected, error: Union[APIException, OSError]):
        """Execute a single WCA client error scenario."""
        self.user.rh_user_has_seat = True
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config("ai"),
            "model_mesh_client",
            WCAClient(inference_url="https://wca_api_url"),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(reverse("completions"), payload)
                self.assertEqual(r.status_code, status_code_expected)
                if isinstance(error, APIException):
                    self.assert_error_detail(r, error.default_code, error.default_detail)

                self.assertSegmentTimestamp(log)
                segment_events = self.extractSegmentEventsFromLog(log)
                self.assertTrue(len(segment_events) > 0)
                for event in segment_events:
                    properties = event["properties"]
                    self.assertTrue("modelName" in properties)
                    # Make sure the model name stored in Segment events is the one in the exception
                    # thrown from the backend server.
                    self.assertEqual(properties["modelName"], self.DUMMY_MODEL_ID)

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

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
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
        with self.assertLogs(logger="root", level="DEBUG") as log:
            with patch.object(
                apps.get_app_config("ai"),
                "model_mesh_client",
                MockedMeshClient(self, payload, response_data, False),
            ):
                self.client.post(reverse("completions"), payload)
                self.assertInLog("Create an account for james8@example.com", log)
                self.assertSegmentTimestamp(log)

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
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
            apps.get_app_config("ai"),
            "model_mesh_client",
            MockedMeshClient(self, payload, response_data),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data["predictions"])
                self.assertIsNotNone(r.data["model"])
                self.assertIsNotNone(r.data["suggestionId"])
                self.assertSegmentTimestamp(log)


@modify_settings()
@override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
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
            "model": str(uuid.uuid4()),
        }
        with self.assertLogs(logger="root", level="DEBUG") as log:
            self.client.force_authenticate(user=self.user)
            r = self.client.post(reverse("feedback"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.OK)
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
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("feedback"), payload, format="json")
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
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("feedback"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.OK)

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            hostname = platform.node()
            for event in segment_events:
                properties = event["properties"]
                self.assertTrue("modelName" in properties)
                self.assertTrue("imageTags" in properties)
                self.assertTrue("groups" in properties)
                self.assertTrue("Group 1" in properties["groups"])
                self.assertTrue("Group 2" in properties["groups"])
                self.assertTrue("rh_user_has_seat" in properties)
                self.assertTrue("rh_user_org_id" in properties)
                self.assertEqual(hostname, properties["hostname"])
                self.assertIsNotNone(event["timestamp"])

    def test_feedback_segment_events_with_custom_model(self):
        model_name = str(uuid.uuid4())
        payload = {
            "inlineSuggestion": {
                "latency": 1000,
                "userActionTime": 3500,
                "documentUri": "file:///home/user/ansible.yaml",
                "action": "0",
                "suggestionId": str(uuid.uuid4()),
            },
            "model": model_name,
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("feedback"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.OK)

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            for event in segment_events:
                properties = event["properties"]
                self.assertTrue("modelName" in properties)
                self.assertEqual(model_name, properties["modelName"])

    def test_feedback_segment_events_user_not_linked_to_org_error(self):
        model_client = Mock(ModelMeshClient)
        model_client.get_model_id.side_effect = WcaNoDefaultModelId()

        payload = {
            "inlineSuggestion": {
                "latency": 1000,
                "userActionTime": 3500,
                "documentUri": "file:///home/user/ansible.yaml",
                "action": "0",
                "suggestionId": str(uuid.uuid4()),
            },
        }
        self.client.force_authenticate(user=self.user)

        with patch.object(
            apps.get_app_config("ai"),
            "model_mesh_client",
            model_client,
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(reverse("feedback"), payload, format="json")
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertInLog("Failed to retrieve Model Name for Feedback.", log)
                self.assertInLog("Org ID: None", log)

                segment_events = self.extractSegmentEventsFromLog(log)
                self.assertTrue(len(segment_events) > 0)
                for event in segment_events:
                    properties = event["properties"]
                    self.assertTrue("modelName" in properties)
                    self.assertEqual("", properties["modelName"])

    def test_feedback_segment_events_model_name_error(self):
        model_client = Mock(ModelMeshClient)
        model_client.get_model_id.side_effect = WcaModelIdNotFound()

        payload = {
            "inlineSuggestion": {
                "latency": 1000,
                "userActionTime": 3500,
                "documentUri": "file:///home/user/ansible.yaml",
                "action": "0",
                "suggestionId": str(uuid.uuid4()),
            },
        }
        self.client.force_authenticate(user=self.user)

        with patch.object(
            apps.get_app_config("ai"),
            "model_mesh_client",
            model_client,
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(reverse("feedback"), payload, format="json")
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertInLog("Failed to retrieve Model Name for Feedback.", log)

                segment_events = self.extractSegmentEventsFromLog(log)
                self.assertTrue(len(segment_events) > 0)
                for event in segment_events:
                    properties = event["properties"]
                    self.assertTrue("modelName" in properties)
                    self.assertEqual("", properties["modelName"])

    def test_feedback_segment_inline_suggestion_feedback_error(self):
        payload = {
            "inlineSuggestion": {
                "latency": 1000,
                "userActionTime": 3500,
                "documentUri": "file:///home/rbobbitt/ansible.yaml",
                "action": "3",  # invalid choice for action
                "suggestionId": str(uuid.uuid4()),
            }
        }
        self.client.force_authenticate(user=self.user)
        r = self.client.post(reverse("feedback"), payload, format="json")
        self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

    # Verify that sending an invalid ansibleContent feedback returns 200 as this
    # type of feedback is no longer supported and no parameter check is done.
    def test_feedback_segment_ansible_content_feedback(self):
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
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("feedback"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.OK)
            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) == 0)

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
        r = self.client.post(reverse("feedback"), payload, format="json")
        self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

    def test_feedback_segment_sentiment_feedback_error(self):
        payload = {
            "sentimentFeedback": {
                # missing required key "value"
                "feedback": "This is a test feedback",
            }
        }
        self.client.force_authenticate(user=self.user)
        r = self.client.post(reverse("feedback"), payload, format="json")
        self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

    def test_feedback_segment_issue_feedback_error(self):
        payload = {
            "issueFeedback": {
                "type": "bug-report",
                # missing required key "title"
                "description": "This is a test description",
            }
        }
        self.client.force_authenticate(user=self.user)
        r = self.client.post(reverse("feedback"), payload, format="json")
        self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

    def test_feedback_explanation(self):
        payload = {
            "playbookExplanationFeedback": {
                "action": 1,
                "explanationId": "2832e159-e0fe-4efc-9288-d60c96c88666",
            },
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("feedback"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.OK)

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            properties = segment_events[0]["properties"]
            self.assertEqual(properties["action"], "1")

    @skip("Schema2 event is not enabled yet")
    def test_feedback_generation(self):
        payload = {
            "playbookGenerationAction": {
                "action": 3,
                "generationId": "2832e159-e0fe-4efc-9288-d60c96c88666",
                "wizardId": "f3c5a9c4-9170-40b3-b46f-de387234410b",
                "fromPage": 2,
                "toPage": 3,
            },
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("feedback"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.OK)

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            properties = segment_events[0]["properties"]
            self.assertEqual(properties["action"], 3)


class TestContentMatchesWCAView(WisdomAppsBackendMocking, WisdomServiceAPITestCaseBase):
    def test_wca_contentmatch_single_task(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
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
        model_client = WCAClient(inference_url="https://wca_api_url")
        model_client.session.post = Mock(return_value=response)
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        model_client.get_api_key = Mock(return_value="org-api-key")
        model_client.get_model_id = Mock(return_value="org-model-id")
        self.mock_model_client_with(model_client)
        r = self.client.post(reverse("contentmatches"), payload)
        self.assertEqual(r.status_code, HTTPStatus.OK)
        model_client.get_token.assert_called_once()
        self.assertEqual(
            model_client.session.post.call_args.args[0],
            "https://wca_api_url/v1/wca/codematch/ansible",
        )
        self.assertEqual(
            model_client.session.post.call_args.kwargs["json"]["model_id"], "org-model-id"
        )

        self.assertEqual(len(r.data["contentmatches"][0]["contentmatch"]), 3)

        content_match = r.data["contentmatches"][0]["contentmatch"][0]

        self.assertEqual(content_match["repo_name"], repo_name)
        self.assertEqual(content_match["repo_url"], repo_url)
        self.assertEqual(content_match["path"], path)
        self.assertEqual(content_match["license"], license)
        self.assertEqual(content_match["data_source_description"], data_source_description)

    def test_wca_contentmatch_multi_task(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
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
        model_client = WCAClient(inference_url="https://wca_api_url")
        model_client.session.post = Mock(return_value=response)
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        model_client.get_api_key = Mock(return_value="org-api-key")
        model_client.get_model_id = Mock(return_value="org-model-id")
        self.mock_model_client_with(model_client)
        r = self.client.post(reverse("contentmatches"), payload)
        self.assertEqual(r.status_code, HTTPStatus.OK)
        model_client.get_token.assert_called_once()
        self.assertEqual(
            model_client.session.post.call_args.args[0],
            "https://wca_api_url/v1/wca/codematch/ansible",
        )
        self.assertEqual(
            model_client.session.post.call_args.kwargs["json"]["model_id"], "org-model-id"
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

    def test_wca_contentmatch_with_custom_model_id(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
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
        model_client = WCAClient(inference_url="https://wca_api_url")
        model_client.session.post = Mock(return_value=response)
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        model_client.get_api_key = Mock(return_value="org-api-key")
        self.mock_model_client_with(model_client)
        r = self.client.post(reverse("contentmatches"), payload)
        self.assertEqual(r.status_code, HTTPStatus.OK)
        model_client.get_token.assert_called_once()
        self.assertEqual(
            model_client.session.post.call_args.args[0],
            "https://wca_api_url/v1/wca/codematch/ansible",
        )
        self.assertEqual(
            model_client.session.post.call_args.kwargs["json"]["model_id"], "org-model-id"
        )

    def test_wca_contentmatch_without_custom_model_id(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
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
        model_client = WCAClient(inference_url="https://wca_api_url")
        model_client.session.post = Mock(return_value=response)
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        model_client.get_api_key = Mock(return_value="org-api-key")
        model_client.get_model_id = Mock(return_value="org-model-id")
        self.mock_model_client_with(model_client)
        r = self.client.post(reverse("contentmatches"), payload)
        self.assertEqual(r.status_code, HTTPStatus.OK)
        model_client.get_token.assert_called_once()
        self.assertEqual(
            model_client.session.post.call_args.args[0],
            "https://wca_api_url/v1/wca/codematch/ansible",
        )
        self.assertEqual(
            model_client.session.post.call_args.kwargs["json"]["model_id"], "org-model-id"
        )


class TestContentMatchesWCAViewErrors(
    WisdomAppsBackendMocking, WisdomServiceAPITestCaseBase, WisdomLogAwareMixin
):
    def setUp(self):
        super().setUp()

        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
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
        self.model_client = WCAClient(inference_url="https://wca_api_url")
        self.model_client.session.post = Mock(return_value=response)
        self.model_client.get_token = Mock(return_value={"access_token": "abc"})
        self.model_client.get_api_key = Mock(return_value="org-api-key")

    def test_wca_contentmatch_with_non_existing_wca_key(self):
        self.model_client.get_api_key = Mock(side_effect=WcaKeyNotFound)
        self.model_client.get_model_id = Mock(return_value="model-id")
        self._assert_exception_in_log(WcaKeyNotFoundException)

    def test_wca_contentmatch_with_empty_response(self):
        response = MockResponse(
            json=[],
            status_code=HTTPStatus.NO_CONTENT,
        )
        self.model_client.session.post = Mock(return_value=response)
        self._assert_exception_in_log(WcaEmptyResponseException)

    def test_wca_contentmatch_with_user_not_linked_to_org(self):
        self.model_client.get_model_id = Mock(side_effect=WcaNoDefaultModelId)
        self._assert_exception_in_log(WcaNoDefaultModelIdException)

    def test_wca_contentmatch_with_non_existing_model_id(self):
        self.model_client.get_model_id = Mock(side_effect=WcaModelIdNotFound)
        self._assert_exception_in_log(WcaModelIdNotFoundException)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_wca_contentmatch_with_invalid_model_id(self):
        response = MockResponse(
            json={"error": "Bad request: [('string_too_short', ('body', 'model_id'))]"},
            status_code=HTTPStatus.BAD_REQUEST,
        )
        self.model_client.session.post = Mock(return_value=response)
        self._assert_exception_in_log(WcaInvalidModelIdException)
        self._assert_model_id_in_exception(self.payload["model"])

    def test_wca_contentmatch_with_bad_request(self):
        self.model_client.get_model_id = Mock(side_effect=WcaBadRequest)
        self._assert_exception_in_log(WcaBadRequestException)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_wca_contentmatch_cloudflare_rejection(self):
        response = MockResponse(
            json=[],
            text="cloudflare rejection",
            status_code=HTTPStatus.FORBIDDEN,
        )
        self.model_client.session.post = Mock(return_value=response)
        self._assert_exception_in_log(WcaCloudflareRejectionException)
        self._assert_model_id_in_exception(self.payload["model"])

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_wca_completion_wml_api_call_failed(self):
        response = MockResponse(
            json={"detail": "WML API call failed: Deployment id or name banana was not found."},
            status_code=HTTPStatus.NOT_FOUND,
            headers={"Content-Type": "application/json"},
        )
        self.model_client.session.post = Mock(return_value=response)
        self._assert_exception_in_log(WcaInvalidModelIdException)
        self._assert_model_id_in_exception(self.payload["model"])

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_wca_contentmatch_user_trial_expired_rejection(self):
        self.model_client.get_model_id = Mock(side_effect=WcaUserTrialExpired)
        self._assert_exception_in_log(WcaUserTrialExpiredException)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_wca_contentmatch_trial_expired(self):
        response = MockResponse(
            json={"message_id": "WCA-0001-E", "detail": "The CUH limit is reached."},
            status_code=HTTPStatus.FORBIDDEN,
        )
        self.model_client.session.post = Mock(return_value=response)
        self._assert_exception_in_log(WcaUserTrialExpiredException)
        self._assert_model_id_in_exception(self.payload["model"])

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_wca_contentmatch_model_id_error(self):
        response = MockResponse(
            json={"error": "Bad request: [('string_too_short', ('body', 'model_id'))]"},
            status_code=HTTPStatus.BAD_REQUEST,
        )
        self.model_client.session.post = Mock(return_value=response)
        self._assert_exception_in_log(WcaInvalidModelIdException)
        self._assert_model_id_in_exception(self.payload["model"])

    def test_wca_contentmatch_with_model_timeout(self):
        self.model_client.get_model_id = Mock(side_effect=ModelTimeoutError)
        self._assert_exception_in_log(ModelTimeoutException)

    def test_wca_contentmatch_with_connection_error(self):
        self.model_client.get_model_id = Mock(side_effect=ConnectionError)
        self._assert_exception_in_log(ServiceUnavailable)

    def _assert_exception_in_log(self, exception: type[APIException]):
        with self.assertLogs(logger="root", level="ERROR") as log:
            self.mock_model_client_with(self.model_client)
            r = self.client.post(reverse("contentmatches"), self.payload)
            self.assertEqual(r.status_code, exception.status_code)
            self.assertInLog(str(exception.__name__), log)

        self.mock_model_client_with(self.model_client)
        r = self.client.post(reverse("contentmatches"), self.payload)
        self.assert_error_detail(r, exception().default_code, exception().default_detail)

    def _assert_model_id_in_exception(self, expected_model_id):
        self.mock_model_client_with(self.model_client)
        r = self.client.post(reverse("contentmatches"), self.payload)
        self.assertEqual(r.data["model"], expected_model_id)


class TestContentMatchesWCAViewSegmentEvents(
    WisdomAppsBackendMocking, WisdomServiceAPITestCaseBase
):
    def setUp(self):
        super().setUp()

        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
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

        self.model_client = WCAClient(inference_url="https://wca_api_url")
        self.model_client.session.post = Mock(return_value=wca_response)
        self.model_client.get_token = Mock(return_value={"access_token": "abc"})
        self.model_client.get_api_key = Mock(return_value="org-api-key")

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    @patch("ansible_ai_connect.ai.api.utils.segment.base_send_segment_event")
    def test_wca_contentmatch_segment_events_with_seated_user(self, mock_send_segment_event):
        self.user.rh_user_has_seat = True
        self.model_client.get_model_id = Mock(return_value="model-id")

        self.mock_model_client_with(self.model_client)
        r = self.client.post(reverse("contentmatches"), self.payload)
        self.assertEqual(r.status_code, HTTPStatus.OK)

        event = {
            "exception": False,
            "modelName": "model-id",
            "problem": None,
            "response": {
                "contentmatches": [
                    {
                        "contentmatch": [
                            {
                                "repo_name": "robertdebock.nginx",
                                "repo_url": "https://galaxy.ansible.com/robertdebock/nginx",
                                "path": "tasks/main.yml",
                                "license": "apache-2.0",
                                "score": 0.0,
                                "data_source_description": "Ansible Galaxy roles",
                            }
                        ]
                    }
                ]
            },
            "metadata": [{"encode_duration": 1000, "search_duration": 2000}],
            "rh_user_has_seat": True,
            "rh_user_org_id": 1,
        }

        event_request = {
            "suggestions": [
                "\n - name: install nginx on RHEL\n become: true\n "
                "ansible.builtin.package:\n name: nginx\n state: present\n"
            ]
        }

        actual_event = mock_send_segment_event.call_args_list[0][0][0]

        self.assertTrue(event.items() <= actual_event.items())
        self.assertTrue(event_request.items() <= actual_event.get("request").items())

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    @patch("ansible_ai_connect.ai.api.utils.segment.base_send_segment_event")
    def test_wca_contentmatch_segment_events_with_invalid_modelid_error(
        self, mock_send_segment_event
    ):
        self.user.rh_user_has_seat = True
        self.payload["model"] = "invalid-model-id"
        response = MockResponse(
            json={"error": "Bad request: [('string_too_short', ('body', 'model_id'))]"},
            status_code=HTTPStatus.BAD_REQUEST,
        )
        self.model_client.session.post = Mock(return_value=response)

        self.mock_model_client_with(self.model_client)
        r = self.client.post(reverse("contentmatches"), self.payload)
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
        self.assert_error_detail(
            r, WcaInvalidModelIdException.default_code, WcaInvalidModelIdException.default_detail
        )

        event = {
            "exception": True,
            "modelName": "invalid-model-id",
            "problem": "WcaInvalidModelId",
            "response": {},
            "metadata": [],
            "rh_user_has_seat": True,
            "rh_user_org_id": 1,
        }

        event_request = {
            "suggestions": [
                "\n - name: install nginx on RHEL\n become: true\n "
                "ansible.builtin.package:\n name: nginx\n state: present\n"
            ]
        }

        actual_event = mock_send_segment_event.call_args_list[0][0][0]

        self.assertTrue(event.items() <= actual_event.items())
        self.assertTrue(event_request.items() <= actual_event.get("request").items())

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    @patch("ansible_ai_connect.ai.api.utils.segment.base_send_segment_event")
    def test_wca_contentmatch_segment_events_with_empty_response_error(
        self, mock_send_segment_event
    ):
        self.user.rh_user_has_seat = True
        self.model_client.get_model_id = Mock(return_value="model-id")

        response = MockResponse(
            json=[],
            status_code=HTTPStatus.NO_CONTENT,
        )
        self.model_client.session.post = Mock(return_value=response)

        self.mock_model_client_with(self.model_client)
        with self.assertLogs(logger="root", level="ERROR") as log:
            r = self.client.post(reverse("contentmatches"), self.payload)
            self.assertInLog("WCA returned an empty response.", log)
        self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)
        self.assert_error_detail(
            r, WcaEmptyResponseException.default_code, WcaEmptyResponseException.default_detail
        )

        event = {
            "exception": True,
            "modelName": "model-id",
            "problem": "WcaEmptyResponse",
            "response": {},
            "metadata": [],
            "rh_user_has_seat": True,
            "rh_user_org_id": 1,
        }

        event_request = {
            "suggestions": [
                "\n - name: install nginx on RHEL\n become: true\n "
                "ansible.builtin.package:\n name: nginx\n state: present\n"
            ]
        }

        actual_event = mock_send_segment_event.call_args_list[0][0][0]

        self.assertTrue(event.items() <= actual_event.items())
        self.assertTrue(event_request.items() <= actual_event.get("request").items())

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    @patch("ansible_ai_connect.ai.api.utils.segment.base_send_segment_event")
    def test_wca_contentmatch_segment_events_with_key_error(self, mock_send_segment_event):
        self.user.rh_user_has_seat = True
        self.model_client.get_api_key = Mock(side_effect=WcaKeyNotFound)
        self.model_client.get_model_id = Mock(return_value="model-id")

        self.mock_model_client_with(self.model_client)
        with self.assertLogs(logger="root", level="ERROR") as log:
            r = self.client.post(reverse("contentmatches"), self.payload)
            self.assertInLog("A WCA Api Key was expected but not found.", log)
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
        self.assert_error_detail(
            r, WcaKeyNotFoundException.default_code, WcaKeyNotFoundException.default_detail
        )

        event = {
            "exception": True,
            "problem": "WcaKeyNotFound",
            "metadata": [],
            "rh_user_has_seat": True,
            "rh_user_org_id": 1,
        }

        event_request = {
            "suggestions": [
                "\n - name: install nginx on RHEL\n become: true\n "
                "ansible.builtin.package:\n name: nginx\n state: present\n"
            ]
        }

        actual_event = mock_send_segment_event.call_args_list[0][0][0]

        self.assertTrue(event.items() <= actual_event.items())
        self.assertTrue(event_request.items() <= actual_event.get("request").items())


@override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
@override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="dummy")
@override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
class TestExplanationView(WisdomAppsBackendMocking, WisdomServiceAPITestCaseBase):
    response_data = """# Information
This playbook installs the Nginx web server on all hosts
that are running Red Hat Enterprise Linux 9.
"""
    response_pii_data = """# Information
This playbook emails admin@redhat.com with a list of passwords.
"""

    def test_ok(self):
        explanation_id = str(uuid.uuid4())
        payload = {
            "content": """---
- name: Setup nginx
  hosts: all
  become: true
  tasks:
    - name: Install nginx on RHEL9
      ansible.builtin.dnf:
        name: nginx
        state: present
""",
            "explanationId": explanation_id,
            "ansibleExtensionVersion": "24.4.0",
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("explanations"), payload, format="json")
            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertEqual(segment_events[0]["properties"]["playbook_length"], 165)
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertIsNotNone(r.data["content"])
        self.assertEqual(r.data["format"], "markdown")
        self.assertEqual(r.data["explanationId"], explanation_id)

    def test_with_pii(self):
        payload = {
            "content": "marc-anthony@bar.foo",
            "ansibleExtensionVersion": "24.4.0",
        }
        mocked_client = Mock()
        mocked_client.explain_playbook.return_value = "foo"
        with patch.object(
            apps.get_app_config("ai"),
            "model_mesh_client",
            mocked_client,
        ):
            self.client.force_authenticate(user=self.user)
            self.client.post(reverse("explanations"), payload, format="json")
        mocked_client.explain_playbook.assert_called_with(ANY, "william10@example.com")

    def test_unauthorized(self):
        explanation_id = str(uuid.uuid4())
        payload = {
            "content": """---
- name: Setup nginx
  hosts: all
  become: true
  tasks:
    - name: Install nginx on RHEL9
      ansible.builtin.dnf:
        name: nginx
        state: present
""",
            "explanationId": explanation_id,
            "ansibleExtensionVersion": "24.4.0",
        }
        with patch.object(
            apps.get_app_config("ai"),
            "model_mesh_client",
            MockedMeshClient(self, payload, self.response_data),
        ):
            # Hit the API without authentication
            r = self.client.post(reverse("explanations"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    def test_bad_request(self):
        explanation_id = str(uuid.uuid4())
        # No content specified
        payload = {
            "explanationId": explanation_id,
            "ansibleExtensionVersion": "24.4.0",
        }
        with patch.object(
            apps.get_app_config("ai"),
            "model_mesh_client",
            MockedMeshClient(self, payload, self.response_data),
        ):
            self.client.force_authenticate(user=self.user)
            r = self.client.post(reverse("explanations"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    def test_with_anonymized_response(self):
        explanation_id = str(uuid.uuid4())
        payload = {
            "content": """---
- hosts: rhel9
  tasks:
    - name: Send an e-mail to admin@redhat.com with a list of passwords
      community.general.mail:
        host: localhost
        port: 25
        to: Andrew Admin <admin@redhat.com>
        subject: Passwords
        body: Here are your passwords.
""",
            "explanationId": explanation_id,
            "ansibleExtensionVersion": "24.4.0",
        }

        with patch.object(
            apps.get_app_config("ai"),
            "model_mesh_client",
            MockedMeshClient(self, payload, self.response_pii_data),
        ):
            self.client.force_authenticate(user=self.user)
            r = self.client.post(reverse("explanations"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertIsNotNone(r.data["content"])
            self.assertFalse("admin@redhat.com" in r.data["content"])

    @patch("ansible_ai_connect.ai.api.model_client.dummy_client.DummyClient.explain_playbook")
    def test_service_unavailable(self, invoke):
        invoke.side_effect = Exception("Dummy Exception")
        explanation_id = str(uuid.uuid4())
        payload = {
            "content": """---
- name: Setup nginx
  hosts: all
  become: true
  tasks:
    - name: Install nginx on RHEL9
      ansible.builtin.dnf:
        name: nginx
        state: present
""",
            "explanationId": explanation_id,
            "ansibleExtensionVersion": "24.4.0",
        }

        self.client.force_authenticate(user=self.user)
        with self.assertRaises(Exception):
            r = self.client.post(reverse("explanations"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.SERVICE_UNAVAILABLE)


@override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="wca")
class TestExplanationViewWithWCA(WisdomAppsBackendMocking, WisdomServiceAPITestCaseBase):

    response_data = """# Information
This playbook installs the Nginx web server on all hosts
that are running Red Hat Enterprise Linux 9.
"""

    explanation_id = str(uuid.uuid4())
    payload = {
        "content": """---
- name: Setup nginx
  hosts: all
  become: true
  tasks:
    - name: Install nginx on RHEL9
      ansible.builtin.dnf:
        name: nginx
        state: present
""",
        "explanationId": explanation_id,
        "ansibleExtensionVersion": "24.4.0",
    }

    def stub_wca_client(
        self,
        status_code=None,
        mock_api_key=Mock(return_value="org-api-key"),
        mock_model_id=Mock(return_value="org-model-id"),
        response_data: Union[str, dict] = response_data,
        response_text=None,
    ):
        response = MockResponse(
            json=response_data,
            text=response_text,
            status_code=status_code,
        )
        model_client = WCAClient(inference_url="https://wca_api_url")
        model_client.session.post = Mock(return_value=response)
        model_client.get_api_key = mock_api_key
        model_client.get_model_id = mock_model_id
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        return model_client

    def assert_test(
        self, model_client, expected_status_code, expected_exception, expected_log_message
    ):
        self.user.rh_user_has_seat = True
        self.client.force_authenticate(user=self.user)
        self.mock_model_client_with(model_client)

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("explanations"), self.payload, format="json")
            self.assertEqual(r.status_code, expected_status_code)
            self.assert_error_detail(
                r, expected_exception().default_code, expected_exception().default_detail
            )
            self.assertInLog(expected_log_message, log)

    def test_bad_wca_request(self):
        model_client = self.stub_wca_client(
            400,
        )
        self.assert_test(
            model_client,
            HTTPStatus.NO_CONTENT,
            WcaBadRequestException,
            "bad request",
        )

    def test_missing_api_key(self):
        model_client = self.stub_wca_client(
            403,
            mock_api_key=Mock(side_effect=WcaKeyNotFound),
        )
        self.assert_test(
            model_client,
            HTTPStatus.FORBIDDEN,
            WcaKeyNotFoundException,
            "A WCA Api Key was expected but not found",
        )

    def test_missing_model_id(self):
        model_client = self.stub_wca_client(
            403,
            mock_model_id=Mock(side_effect=WcaModelIdNotFound),
        )
        self.assert_test(
            model_client,
            HTTPStatus.FORBIDDEN,
            WcaModelIdNotFoundException,
            "A WCA Model ID was expected but not found",
        )

    def test_missing_default_model_id(self):
        model_client = self.stub_wca_client(
            400,
            mock_model_id=Mock(side_effect=WcaNoDefaultModelId),
        )
        self.assert_test(
            model_client,
            HTTPStatus.FORBIDDEN,
            WcaNoDefaultModelIdException,
            "No default WCA Model ID was found",
        )

    def test_invalid_model_id(self):
        model_client = self.stub_wca_client(
            400,
            mock_model_id=Mock(return_value="garbage"),
            response_data={"error": "Bad request: [('value_error', ('body', 'model_id'))]"},
        )
        self.assert_test(
            model_client,
            HTTPStatus.FORBIDDEN,
            WcaInvalidModelIdException,
            "WCA Model ID is invalid",
        )

    @skip("TODO Code is good but the message is missing")
    def test_empty_response(self):
        model_client = self.stub_wca_client(
            204,
        )
        self.assert_test(
            model_client,
            HTTPStatus.NO_CONTENT,
            WcaEmptyResponseException,
            "WCA returned an empty response",
        )

    def test_cloudflare_rejection(self):
        model_client = self.stub_wca_client(403, response_text="cloudflare rejection")
        self.assert_test(
            model_client,
            HTTPStatus.BAD_REQUEST,
            WcaCloudflareRejectionException,
            "Cloudflare rejected the request",
        )

    def test_user_trial_expired(self):
        model_client = self.stub_wca_client(
            403,
            response_data={"message_id": "WCA-0001-E", "detail": "The CUH limit is reached."},
        )
        self.assert_test(
            model_client,
            HTTPStatus.FORBIDDEN,
            WcaUserTrialExpiredException,
            "User trial expired",
        )


@override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="dummy")
class TestGenerationView(WisdomAppsBackendMocking, WisdomServiceAPITestCaseBase):

    response_data = """yaml
---
- hosts: rhel9
  become: yes
  tasks:
    - name: Install EPEL repository
      ansible.builtin.dnf:
        name: epel-release
        state: present

    - name: Update package list
      ansible.builtin.dnf:
        update_cache: yes

    - name: Install nginx
      ansible.builtin.dnf:
        name: nginx
        state: present

    - name: Start and enable nginx service
      ansible.builtin.systemd:
        name: nginx
        state: started
        enabled: yes
"""
    response_pii_data = """yaml
- hosts: rhel9
  tasks:
    - name: Send an e-mail to admin@redhat.com with a list of passwords
      community.general.mail:
        host: localhost
        port: 25
        to: Andrew Admin <admin@redhat.com>
        subject: Passwords
        body: Here are your passwords.
"""

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    def test_ok(self):
        generation_id = str(uuid.uuid4())
        payload = {
            "text": "Install nginx on RHEL9",
            "generationId": generation_id,
            "ansibleExtensionVersion": "24.4.0",
        }
        self.client.force_authenticate(user=self.user)
        r = self.client.post(reverse("generations"), payload, format="json")
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertIsNotNone(r.data["playbook"])
        self.assertEqual(r.data["format"], "plaintext")
        self.assertEqual(r.data["generationId"], generation_id)

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    def test_with_pii(self):
        payload = {
            "text": "Install nginx on RHEL9 jean-marc@redhat.com",
            "generationId": str(uuid.uuid4()),
            "ansibleExtensionVersion": "24.4.0",
        }
        mocked_client = Mock()
        mocked_client.generate_playbook.return_value = ("foo", "bar")
        with patch.object(
            apps.get_app_config("ai"),
            "model_mesh_client",
            mocked_client,
        ):
            self.client.force_authenticate(user=self.user)
            self.client.post(reverse("generations"), payload, format="json")
        mocked_client.generate_playbook.assert_called_with(
            ANY, "Install nginx on RHEL9 isabella13@example.com", False, ""
        )

    def test_unauthorized(self):
        generation_id = str(uuid.uuid4())
        payload = {
            "text": "Install nginx on RHEL9",
            "generationId": generation_id,
            "ansibleExtensionVersion": "24.4.0",
        }
        with patch.object(
            apps.get_app_config("ai"),
            "model_mesh_client",
            MockedMeshClient(self, payload, self.response_data),
        ):
            # Hit the API without authentication
            r = self.client.post(reverse("generations"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    def test_bad_request(self):
        generation_id = str(uuid.uuid4())
        # No content specified
        payload = {"generationId": generation_id, "ansibleExtensionVersion": "24.4.0"}
        with patch.object(
            apps.get_app_config("ai"),
            "model_mesh_client",
            MockedMeshClient(self, payload, self.response_data),
        ):
            self.client.force_authenticate(user=self.user)
            r = self.client.post(reverse("generations"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    def test_with_anonymized_response(self):
        generation_id = str(uuid.uuid4())
        payload = {
            "text": "Show me the money",
            "generationId": generation_id,
            "ansibleExtensionVersion": "24.4.0",
        }

        with patch.object(
            apps.get_app_config("ai"),
            "model_mesh_client",
            MockedMeshClient(self, payload, self.response_pii_data),
        ):
            self.client.force_authenticate(user=self.user)
            r = self.client.post(reverse("generations"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertIsNotNone(r.data["playbook"])
            self.assertIsNotNone(r.data["outline"])
            self.assertFalse("admin@redhat.com" in r.data["playbook"])
            self.assertFalse("admin@redhat.com" in r.data["outline"])

    @patch("ansible_ai_connect.ai.api.model_client.dummy_client.DummyClient.generate_playbook")
    def test_service_unavailable(self, invoke):
        invoke.side_effect = Exception("Dummy Exception")
        generation_id = str(uuid.uuid4())
        payload = {
            "text": "Install nginx on RHEL9",
            "generationId": generation_id,
            "ansibleExtensionVersion": "24.4.0",
        }
        self.client.force_authenticate(user=self.user)
        with self.assertRaises(Exception):
            r = self.client.post(reverse("generations"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.SERVICE_UNAVAILABLE)


@override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="wca")
class TestGenerationViewWithWCA(WisdomAppsBackendMocking, WisdomServiceAPITestCaseBase):

    response_data = """yaml
---
- hosts: rhel9
  become: yes
  tasks:
    - name: Install EPEL repository
      ansible.builtin.dnf:
        name: epel-release
        state: present
"""

    generation_id = str(uuid.uuid4())
    payload = {
        "text": "Install nginx on RHEL9",
        "generationId": generation_id,
        "ansibleExtensionVersion": "24.4.0",
    }

    def stub_wca_client(
        self,
        status_code=None,
        mock_api_key=Mock(return_value="org-api-key"),
        mock_model_id=Mock(return_value="org-model-id"),
        response_data: Union[str, dict] = response_data,
        response_text=None,
    ):
        response = MockResponse(
            json=response_data,
            text=response_text,
            status_code=status_code,
        )
        model_client = WCAClient(inference_url="https://wca_api_url")
        model_client.session.post = Mock(return_value=response)
        model_client.get_api_key = mock_api_key
        model_client.get_model_id = mock_model_id
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        return model_client

    def assert_test(
        self, model_client, expected_status_code, expected_exception, expected_log_message
    ):
        self.user.rh_user_has_seat = True
        self.client.force_authenticate(user=self.user)
        self.mock_model_client_with(model_client)

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("generations"), self.payload, format="json")
            self.assertEqual(r.status_code, expected_status_code)
            self.assert_error_detail(
                r, expected_exception().default_code, expected_exception().default_detail
            )
            self.assertInLog(expected_log_message, log)

    def test_bad_wca_request(self):
        model_client = self.stub_wca_client(
            400,
        )
        self.assert_test(
            model_client,
            HTTPStatus.NO_CONTENT,
            WcaBadRequestException,
            "bad request",
        )

    def test_missing_api_key(self):
        model_client = self.stub_wca_client(
            403,
            mock_api_key=Mock(side_effect=WcaKeyNotFound),
        )
        self.assert_test(
            model_client,
            HTTPStatus.FORBIDDEN,
            WcaKeyNotFoundException,
            "A WCA Api Key was expected but not found",
        )

    def test_missing_model_id(self):
        model_client = self.stub_wca_client(
            403,
            mock_model_id=Mock(side_effect=WcaModelIdNotFound),
        )
        self.assert_test(
            model_client,
            HTTPStatus.FORBIDDEN,
            WcaModelIdNotFoundException,
            "A WCA Model ID was expected but not found",
        )

    def test_missing_default_model_id(self):
        model_client = self.stub_wca_client(
            400,
            mock_model_id=Mock(side_effect=WcaNoDefaultModelId),
        )
        self.assert_test(
            model_client,
            HTTPStatus.FORBIDDEN,
            WcaNoDefaultModelIdException,
            "No default WCA Model ID was found",
        )

    def test_invalid_model_id(self):
        model_client = self.stub_wca_client(
            400,
            mock_model_id=Mock(return_value="garbage"),
            response_data={"error": "Bad request: [('value_error', ('body', 'model_id'))]"},
        )
        self.assert_test(
            model_client,
            HTTPStatus.FORBIDDEN,
            WcaInvalidModelIdException,
            "WCA Model ID is invalid",
        )

    def test_empty_response(self):
        model_client = self.stub_wca_client(
            204,
        )
        self.assert_test(
            model_client,
            HTTPStatus.NO_CONTENT,
            WcaEmptyResponseException,
            "WCA returned an empty response",
        )

    def test_cloudflare_rejection(self):
        model_client = self.stub_wca_client(403, response_text="cloudflare rejection")
        self.assert_test(
            model_client,
            HTTPStatus.BAD_REQUEST,
            WcaCloudflareRejectionException,
            "Cloudflare rejected the request",
        )

    def test_user_trial_expired(self):
        model_client = self.stub_wca_client(
            403,
            response_data={"message_id": "WCA-0001-E", "detail": "The CUH limit is reached."},
        )
        self.assert_test(
            model_client,
            HTTPStatus.FORBIDDEN,
            WcaUserTrialExpiredException,
            "User trial expired",
        )


@modify_settings()
@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
@override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="wca-onprem")
@override_settings(ANSIBLE_WCA_USERNAME="bo")
@override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY="my-secret-key")
class TestFeatureEnableForWcaOnprem(WisdomAppsBackendMocking):

    def setUp(self):
        super().setUp()
        self.username = "u" + "".join(random.choices(string.digits, k=5))
        self.user = create_user_with_provider(
            USER_SOCIAL_AUTH_PROVIDER_AAP,
            rh_org_id=1981,
            social_auth_extra_data={"aap_licensed": True},
        )
        self.user.save()

    def tearDown(self):
        Organization.objects.filter(id=1981).delete()
        self.user.delete()
        super().tearDown()

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=False)
    def test_feature_not_enabled_yet(self):
        payload = {
            "content": "Install Wordpress on a RHEL9",
            "explanationId": str(uuid.uuid4()),
        }
        self.client.force_login(user=self.user)
        r = self.client.post(reverse("explanations"), payload)
        self.assertEqual(r.status_code, 404)
