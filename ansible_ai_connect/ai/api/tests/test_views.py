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
from typing import Optional, Union
from unittest import mock, skip
from unittest.mock import Mock, patch

import requests
from django.apps import apps
from django.conf import settings
from django.test import modify_settings, override_settings
from django.urls import reverse
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.runnables.utils import Input, Output
from requests.exceptions import ReadTimeout
from rest_framework.exceptions import APIException

from ansible_ai_connect.ai.api.data.data_model import APIPayload
from ansible_ai_connect.ai.api.exceptions import (
    ChatbotForbiddenException,
    ChatbotInternalServerException,
    ChatbotInvalidRequestException,
    ChatbotInvalidResponseException,
    ChatbotNotEnabledException,
    ChatbotPromptTooLongException,
    ChatbotUnauthorizedException,
    ChatbotValidationException,
    FeedbackValidationException,
    ModelTimeoutException,
    PostprocessException,
    PreprocessInvalidYamlException,
    ServiceUnavailable,
    WcaBadRequestException,
    WcaCloudflareRejectionException,
    WcaEmptyResponseException,
    WcaHAPFilterRejectionException,
    WcaInstanceDeletedException,
    WcaInvalidModelIdException,
    WcaKeyNotFoundException,
    WcaModelIdNotFoundException,
    WcaNoDefaultModelIdException,
    WcaRequestIdCorrelationFailureException,
    WcaUserTrialExpiredException,
)
from ansible_ai_connect.ai.api.model_pipelines.exceptions import (
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
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    CompletionsParameters,
    CompletionsResponse,
    ContentMatchParameters,
    ContentMatchResponse,
    ModelPipelineCompletions,
    ModelPipelineContentMatch,
    ModelPipelinePlaybookExplanation,
    ModelPipelinePlaybookGeneration,
    PlaybookExplanationParameters,
    PlaybookExplanationResponse,
    PlaybookGenerationParameters,
    PlaybookGenerationResponse,
)
from ansible_ai_connect.ai.api.model_pipelines.tests.test_wca_client import (
    WCA_REQUEST_ID_HEADER,
    MockResponse,
)
from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_saas import (
    WCASaaSCompletionsPipeline,
    WCASaaSContentMatchPipeline,
    WCASaaSPlaybookExplanationPipeline,
    WCASaaSPlaybookGenerationPipeline,
)
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
from ansible_ai_connect.main.tests.test_views import create_user_with_provider
from ansible_ai_connect.organizations.models import Organization
from ansible_ai_connect.test_utils import (
    WisdomAppsBackendMocking,
    WisdomLogAwareMixin,
    WisdomServiceAPITestCaseBase,
)
from ansible_ai_connect.users.constants import USER_SOCIAL_AUTH_PROVIDER_AAP
from ansible_ai_connect.users.models import User

logger = logging.getLogger(__name__)

DEFAULT_SUGGESTION_ID = uuid.uuid4()


class MockedLLM(Runnable):
    def __init__(self, response_data):
        self.response_data = response_data

    def invoke(self, input: Input, config: Optional[RunnableConfig] = None) -> Output:
        return self.response_data


class MockedPipelineCompletions(ModelPipelineCompletions):

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
                api_payload.original_prompt = payload["prompt"]

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
                pass

        self.response_data = response_data

    def get_model_id(
        self,
        user: User = None,
        organization_id: Optional[int] = None,
        requested_model_id: str = "",
    ) -> str:
        return requested_model_id or ""

    def invoke(self, params: CompletionsParameters) -> CompletionsResponse:
        model_input = params.model_input
        if self.test_inference_match:
            self.test.assertEqual(model_input, self.expects)
        time.sleep(0.1)  # w/o this line test_rate_limit() fails...
        # i.e., still receives 200 after 10 API calls...
        return self.response_data

    def infer_from_parameters(self, api_key, model_id, context, prompt, suggestion_id=None):
        raise NotImplementedError


class MockedPipelineContentMatch(ModelPipelineContentMatch):

    def __init__(self):
        super().__init__(inference_url="dummy inference url")

    def invoke(self, params: ContentMatchParameters) -> ContentMatchResponse:
        raise NotImplementedError


class MockedPipelinePlaybookGeneration(ModelPipelinePlaybookGeneration):

    def __init__(self, response_data):
        super().__init__(inference_url="dummy inference url")
        self.response_data = response_data

    def invoke(self, params: PlaybookGenerationParameters) -> PlaybookGenerationResponse:
        return self.response_data, self.response_data, []


class MockedPipelinePlaybookExplanation(ModelPipelinePlaybookExplanation):

    def __init__(self, response_data):
        super().__init__(inference_url="dummy inference url")
        self.response_data = response_data

    def invoke(self, params: PlaybookExplanationParameters) -> PlaybookExplanationResponse:
        return self.response_data


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
        model_client = WCASaaSCompletionsPipeline(inference_url="https://wca_api_url")
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
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
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
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
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
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
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
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
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
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
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
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
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
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
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
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
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
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
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
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
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
    def test_wca_completion_seated_user_hap_filter_rejection(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        model_client, model_input = self.stub_wca_client()
        response = MockResponse(
            json={"detail": "our filters detected a potential problem with entities in your input"},
            status_code=HTTPStatus.BAD_REQUEST,
        )
        model_client.session.post = Mock(return_value=response)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(reverse("completions"), model_input)
                self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
                self.assert_error_detail(
                    r,
                    WcaHAPFilterRejectionException.default_code,
                    WcaHAPFilterRejectionException.default_detail,
                )
                self.assertInLog("WCA Hate, Abuse, and Profanity filter rejected the request", log)

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
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
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
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
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
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
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
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
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
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
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
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
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
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
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
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
                self.assert_error_detail(
                    r,
                    WcaRequestIdCorrelationFailureException.default_code,
                    WcaRequestIdCorrelationFailureException.default_detail,
                )
                segment_events = self.extractSegmentEventsFromLog(log)
                self.assertTrue(len(segment_events) > 0)
                for event in segment_events:
                    if event["event"] == "prediction":
                        properties = event["properties"]
                        self.assertTrue(properties["exception"])
                        self.assertEqual(properties["problem"], "WcaRequestIdCorrelationFailure")
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
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
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

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_wca_completion_wca_instance_deleted(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        model_client, model_input = self.stub_wca_client()
        response = MockResponse(
            json={
                "detail": (
                    "Failed to get remaining capacity from Metering API: "
                    "The WCA instance 'banana' has been deleted."
                )
            },
            status_code=HTTPStatus.NOT_FOUND,
        )
        model_client.session.post = Mock(return_value=response)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(reverse("completions"), model_input)
                self.assertEqual(r.status_code, HTTPStatus.IM_A_TEAPOT)
                self.assert_error_detail(
                    r,
                    WcaInstanceDeletedException.default_code,
                    WcaInstanceDeletedException.default_detail,
                )
                self.assertInLog("WCA Instance has been deleted", log)


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
            "model_id": settings.ANSIBLE_AI_MODEL_MESH_MODEL_ID,
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=MockedPipelineCompletions(self, payload, response_data)),
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
            "model_id": settings.ANSIBLE_AI_MODEL_MESH_MODEL_ID,
            "predictions": [
                "- name:  Install Apache\n  ansible.builtin.apt:\n    name: apache2\n    state: latest\n- name:  start Apache\n  ansible.builtin.service:\n    name: apache2\n    state: started\n    enabled: yes\n"  # noqa: E501
            ],
        }
        self.user.rh_user_has_seat = True
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(
                return_value=MockedPipelineCompletions(
                    self, payload, response_data, rh_user_has_seat=True
                )
            ),
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
            "model_id": settings.ANSIBLE_AI_MODEL_MESH_MODEL_ID,
            "predictions": [
                "    - name:  Install Apache\n      ansible.builtin.apt:\n        name: apache2\n        state: latest\n    - name:  say hello test@example.com\n      ansible.builtin.debug:\n        msg: Hello there olivia1@example.com\n"  # noqa: E501
            ],
        }
        self.user.rh_user_has_seat = True
        self.client.force_authenticate(user=self.user)
        # test_inference_match=False because anonymizer changes the prompt before calling WCA
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(
                return_value=MockedPipelineCompletions(
                    self, payload, response_data, test_inference_match=False, rh_user_has_seat=True
                )
            ),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data["predictions"])
                self.assertIn(pii_task.capitalize(), r.data["predictions"][0])
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
            "model_id": settings.ANSIBLE_AI_MODEL_MESH_MODEL_ID,
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=MockedPipelineCompletions(self, payload, response_data)),
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
            "model_id": settings.ANSIBLE_AI_MODEL_MESH_MODEL_ID,
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=MockedPipelineCompletions(self, payload, response_data)),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
                self.assertSegmentTimestamp(log)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_authentication_error(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": settings.ANSIBLE_AI_MODEL_MESH_MODEL_ID,
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        # self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=MockedPipelineCompletions(self, payload, response_data)),
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
            "model_id": settings.ANSIBLE_AI_MODEL_MESH_MODEL_ID,
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=MockedPipelineCompletions(self, payload, response_data)),
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

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    def test_completions_preprocessing_error_without_name_prompt(self):
        payload = {
            "prompt": "---\n  - Name: [Setup]",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": settings.ANSIBLE_AI_MODEL_MESH_MODEL_ID,
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=MockedPipelineCompletions(self, payload, response_data)),
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
            "model_id": settings.ANSIBLE_AI_MODEL_MESH_MODEL_ID,
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=MockedPipelineCompletions(self, payload, response_data)),
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
            "model_id": settings.ANSIBLE_AI_MODEL_MESH_MODEL_ID,
            "predictions": [
                '      ansible.builtin.apt:\n        name: apache2\n      register: "test'
            ],
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger="root", level="INFO") as log:
            with patch.object(
                apps.get_app_config("ai"),
                "get_model_pipeline",
                Mock(return_value=MockedPipelineCompletions(self, payload, response_data)),
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
            "model_id": settings.ANSIBLE_AI_MODEL_MESH_MODEL_ID,
            "predictions": ["      ansible.builtin.apt:\n garbage       name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger="root", level="ERROR") as log:  # Suppress debug output
            with patch.object(
                apps.get_app_config("ai"),
                "get_model_pipeline",
                Mock(return_value=MockedPipelineCompletions(self, payload, response_data)),
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
                "get_model_pipeline",
                Mock(return_value=MockedPipelineCompletions(self, payload, response_data)),
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
                            "RuleID=W018, error=Invalid task structure: "
                            "no module name found",
                            event["properties"]["problem"],
                        )
                    self.assertIsNotNone(event["timestamp"])

    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=False)
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_full_payload_without_ansible_lint_with_commercial_user(self):
        self.user.rh_user_has_seat = True
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": settings.ANSIBLE_AI_MODEL_MESH_MODEL_ID,
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(
                return_value=MockedPipelineCompletions(
                    self, payload, response_data, rh_user_has_seat=True
                )
            ),
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
            "get_model_pipeline",
            Mock(
                return_value=MockedPipelineCompletions(
                    self, payload, response_data, rh_user_has_seat=True
                )
            ),
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
            "get_model_pipeline",
            Mock(
                return_value=MockedPipelineCompletions(
                    self, payload, response_data, rh_user_has_seat=True
                )
            ),
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
    @patch(
        "ansible_ai_connect.ai.api.model_pipelines.wca."
        "pipelines_saas.WCASaaSCompletionsPipeline.invoke"
    )
    def test_wca_client_errors(self, invoke):
        """Run WCA client error scenarios for various errors."""
        for error, status_code_expected in [
            (ModelTimeoutError(), HTTPStatus.NO_CONTENT),
            (WcaBadRequest(), HTTPStatus.NO_CONTENT),
            (WcaInvalidModelId(), HTTPStatus.FORBIDDEN),
            (WcaKeyNotFound(), HTTPStatus.FORBIDDEN),
            (WcaNoDefaultModelId(), HTTPStatus.FORBIDDEN),
            (WcaModelIdNotFound(), HTTPStatus.FORBIDDEN),
            (WcaEmptyResponse(), HTTPStatus.NO_CONTENT),
            (ConnectionError(), HTTPStatus.SERVICE_UNAVAILABLE),
        ]:
            invoke.side_effect = self.get_side_effect(error)
            self.run_wca_client_error_case(status_code_expected, error)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    @patch(
        "ansible_ai_connect.ai.api.model_pipelines.wca."
        "pipelines_saas.WCASaaSCompletionsPipeline.invoke"
    )
    def test_wca_client_postprocess_error(self, invoke):
        invoke.return_value = {"predictions": [""], "model_id": self.DUMMY_MODEL_ID}
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
            "get_model_pipeline",
            Mock(return_value=WCASaaSCompletionsPipeline(inference_url="https://wca_api_url")),
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
            "model_id": settings.ANSIBLE_AI_MODEL_MESH_MODEL_ID,
            "predictions": [""],
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            with patch.object(
                apps.get_app_config("ai"),
                "get_model_pipeline",
                Mock(return_value=MockedPipelineCompletions(self, payload, response_data, False)),
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
            "model_id": "wisdom",
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=MockedPipelineCompletions(self, payload, response_data)),
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
                "userActionTime": 3500,
                "documentUri": "file:///home/user/ansible.yaml",
                "action": "0",
                "suggestionId": str(uuid.uuid4()),
            },
            "ansibleContent": {
                "content": "---\n- hosts: all\n  become: yes\n\n  "
                "tasks:\n    - name: Install Apache\n",
                "documentUri": "file:///home/user/ansible.yaml",
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
        model_client = Mock(WCASaaSCompletionsPipeline)
        model_client.get_model_id.side_effect = WcaNoDefaultModelId()

        payload = {
            "inlineSuggestion": {
                "userActionTime": 3500,
                "documentUri": "file:///home/user/ansible.yaml",
                "action": "0",
                "suggestionId": str(uuid.uuid4()),
            },
        }
        self.client.force_authenticate(user=self.user)

        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
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
        model_client = Mock(WCASaaSCompletionsPipeline)
        model_client.get_model_id.side_effect = WcaModelIdNotFound()

        payload = {
            "inlineSuggestion": {
                "userActionTime": 3500,
                "documentUri": "file:///home/user/ansible.yaml",
                "action": "0",
                "suggestionId": str(uuid.uuid4()),
            },
        }
        self.client.force_authenticate(user=self.user)

        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
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
                "userActionTime": 3500,
                "documentUri": "file:///home/rbobbitt/ansible.yaml",
                "action": "3",  # invalid choice for action
                "suggestionId": str(uuid.uuid4()),
            }
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("feedback"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assert_error_detail(r, FeedbackValidationException.default_code)

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            for event in segment_events:
                self.assertTrue("inlineSuggestionFeedback", event["event"])
                properties = event["properties"]
                self.assertTrue("data" in properties)
                self.assertTrue("exception" in properties)
                self.assertEqual(
                    "file:///home/ano-user/ansible.yaml",
                    properties["data"]["inlineSuggestion"]["documentUri"],
                )
                self.assertIsNotNone(event["timestamp"])

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
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("feedback"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assert_error_detail(r, FeedbackValidationException.default_code)

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            for event in segment_events:
                self.assertTrue("suggestionQualityFeedback", event["event"])
                properties = event["properties"]
                self.assertTrue("data" in properties)
                self.assertTrue("exception" in properties)
                self.assertEqual(
                    "Package name is changed",
                    properties["data"]["suggestionQualityFeedback"]["additionalComment"],
                )
                self.assertIsNotNone(event["timestamp"])

    def test_feedback_segment_sentiment_feedback_error(self):
        payload = {
            "sentimentFeedback": {
                # missing required key "value"
                "feedback": "This is a test feedback",
            }
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("feedback"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assert_error_detail(r, FeedbackValidationException.default_code)

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            for event in segment_events:
                self.assertTrue("suggestionQualityFeedback", event["event"])
                properties = event["properties"]
                self.assertTrue("data" in properties)
                self.assertTrue("exception" in properties)
                self.assertEqual(
                    "This is a test feedback",
                    properties["data"]["sentimentFeedback"]["feedback"],
                )
                self.assertIsNotNone(event["timestamp"])

    def test_feedback_segment_issue_feedback_error(self):
        payload = {
            "issueFeedback": {
                "type": "bug-report",
                # missing required key "title"
                "description": "This is a test description",
            }
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("feedback"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assert_error_detail(r, FeedbackValidationException.default_code)

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            for event in segment_events:
                self.assertTrue("issueFeedback", event["event"])
                properties = event["properties"]
                self.assertTrue("data" in properties)
                self.assertTrue("exception" in properties)
                self.assertEqual(
                    "This is a test description",
                    properties["data"]["issueFeedback"]["description"],
                )
                self.assertIsNotNone(event["timestamp"])

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
        model_client = WCASaaSContentMatchPipeline(inference_url="https://wca_api_url")
        model_client.session.post = Mock(return_value=response)
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        model_client.get_api_key = Mock(return_value="org-api-key")
        model_client.get_model_id = Mock(return_value="org-model-id")
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
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
        model_client = WCASaaSContentMatchPipeline(inference_url="https://wca_api_url")
        model_client.session.post = Mock(return_value=response)
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        model_client.get_api_key = Mock(return_value="org-api-key")
        model_client.get_model_id = Mock(return_value="org-model-id")
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
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
        model_client = WCASaaSContentMatchPipeline(inference_url="https://wca_api_url")
        model_client.session.post = Mock(return_value=response)
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        model_client.get_api_key = Mock(return_value="org-api-key")
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
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
        model_client = WCASaaSContentMatchPipeline(inference_url="https://wca_api_url")
        model_client.session.post = Mock(return_value=response)
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        model_client.get_api_key = Mock(return_value="org-api-key")
        model_client.get_model_id = Mock(return_value="org-model-id")
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
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
        self.model_client = WCASaaSContentMatchPipeline(inference_url="https://wca_api_url")
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
    def test_wca_contentmatch_instance_deleted(self):
        response = MockResponse(
            json={
                "detail": (
                    "Failed to get remaining capacity from Metering API: "
                    "The WCA instance 'banana' has been deleted."
                )
            },
            status_code=HTTPStatus.NOT_FOUND,
        )
        self.model_client.session.post = Mock(return_value=response)
        self._assert_exception_in_log(WcaInstanceDeletedException)
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
            with patch.object(
                apps.get_app_config("ai"),
                "get_model_pipeline",
                Mock(return_value=self.model_client),
            ):
                r = self.client.post(reverse("contentmatches"), self.payload)
                self.assertEqual(r.status_code, exception.status_code)
            self.assertInLog(str(exception.__name__), log)

        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=self.model_client),
        ):
            r = self.client.post(reverse("contentmatches"), self.payload)
            self.assert_error_detail(r, exception().default_code, exception().default_detail)

    def _assert_model_id_in_exception(self, expected_model_id):
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=self.model_client),
        ):
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

        self.model_client = WCASaaSContentMatchPipeline(inference_url="https://wca_api_url")
        self.model_client.session.post = Mock(return_value=wca_response)
        self.model_client.get_token = Mock(return_value={"access_token": "abc"})
        self.model_client.get_api_key = Mock(return_value="org-api-key")

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    @patch("ansible_ai_connect.ai.api.views.send_segment_event")
    def test_wca_contentmatch_segment_events_with_seated_user(self, mock_send_segment_event):
        self.user.rh_user_has_seat = True
        self.model_client.get_model_id = Mock(return_value="model-id")

        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=self.model_client),
        ):
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
    @patch("ansible_ai_connect.ai.api.views.send_segment_event")
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

        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=self.model_client),
        ):
            r = self.client.post(reverse("contentmatches"), self.payload)
            self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
            self.assert_error_detail(
                r,
                WcaInvalidModelIdException.default_code,
                WcaInvalidModelIdException.default_detail,
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
    @patch("ansible_ai_connect.ai.api.views.send_segment_event")
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

        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=self.model_client),
        ):
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
    @patch("ansible_ai_connect.ai.api.views.send_segment_event")
    def test_wca_contentmatch_segment_events_with_key_error(self, mock_send_segment_event):
        self.user.rh_user_has_seat = True
        self.model_client.get_api_key = Mock(side_effect=WcaKeyNotFound)
        self.model_client.get_model_id = Mock(return_value="model-id")

        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=self.model_client),
        ):
            with self.assertLogs(logger="root", level="ERROR") as log:
                r = self.client.post(reverse("contentmatches"), self.payload)
                self.assertInLog("A WCA Api Key was expected but not found.", log)
            self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
            self.assert_error_detail(
                r, WcaKeyNotFoundException.default_code, WcaKeyNotFoundException.default_detail
            )

        event = {
            "exception": True,
            "modelName": "",
            "problem": "WcaKeyNotFound",
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

    def test_ok_with_model_id(self):
        explanation_id = str(uuid.uuid4())
        model = "mymodel"
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
            "model": model,
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("explanations"), payload, format="json")
            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertEqual(segment_events[0]["properties"]["playbook_length"], 197)
            self.assertEqual(segment_events[0]["properties"]["modelName"], "mymodel")
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
        mocked_client.invoke.return_value = "foo"
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=mocked_client),
        ):
            self.client.force_authenticate(user=self.user)
            self.client.post(reverse("explanations"), payload, format="json")

        args: PlaybookExplanationParameters = mocked_client.invoke.call_args[0][0]
        self.assertEqual(args.content, "william10@example.com")

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
            "get_model_pipeline",
            Mock(return_value=MockedPipelinePlaybookExplanation(self.response_data)),
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
            "get_model_pipeline",
            Mock(return_value=MockedPipelinePlaybookExplanation(self.response_data)),
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
            "get_model_pipeline",
            Mock(return_value=MockedPipelinePlaybookExplanation(self.response_pii_data)),
        ):
            self.client.force_authenticate(user=self.user)
            r = self.client.post(reverse("explanations"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertIsNotNone(r.data["content"])
            self.assertFalse("admin@redhat.com" in r.data["content"])

    @patch(
        "ansible_ai_connect.ai.api.model_pipelines.dummy.pipelines."
        "DummyPlaybookExplanationPipeline.invoke"
    )
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

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    def test_with_custom_prompt_valid(self):
        payload = {
            "content": "marc-anthony@bar.foo",
            "customPrompt": "Please explain this {playbook}",
            "ansibleExtensionVersion": "24.4.0",
        }
        mocked_client = Mock()
        mocked_client.invoke.return_value = "foo"
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=mocked_client),
        ):
            self.client.force_authenticate(user=self.user)
            self.client.post(reverse("explanations"), payload, format="json")

        args: PlaybookExplanationParameters = mocked_client.invoke.call_args[0][0]
        self.assertEqual(args.content, "william10@example.com")
        self.assertEqual(args.custom_prompt, "Please explain this {playbook}")

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    def test_with_custom_prompt_blank(self):
        payload = {
            "content": "marc-anthony@bar.foo",
            "customPrompt": "",
            "ansibleExtensionVersion": "24.4.0",
        }
        mocked_client = Mock()
        mocked_client.explain_playbook.return_value = "foo"
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=mocked_client),
        ):
            self.client.force_authenticate(user=self.user)
            r = self.client.post(reverse("explanations"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assertFalse(mocked_client.invoke.called)
            self.assertIn("detail", r.data)
            self.assertIn("customPrompt", r.data["detail"])
            self.assertIn("This field may not be blank.", str(r.data["detail"]["customPrompt"]))

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    def test_with_custom_prompt_missing_playbook(self):
        payload = {
            "content": "marc-anthony@bar.foo",
            "customPrompt": "Please explain this",
            "ansibleExtensionVersion": "24.4.0",
        }
        mocked_client = Mock()
        mocked_client.explain_playbook.return_value = "foo"
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=mocked_client),
        ):
            self.client.force_authenticate(user=self.user)
            r = self.client.post(reverse("explanations"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assertFalse(mocked_client.explain_playbook.called)
            self.assertIn("detail", r.data)
            self.assertIn("customPrompt", r.data["detail"])
            self.assertIn("'{playbook}' placeholder expected.", r.data["detail"]["customPrompt"])


@override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="wca")
@override_settings(ANSIBLE_AI_ENABLE_PLAYBOOK_ENDPOINT=True)
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
        model_client = WCASaaSPlaybookExplanationPipeline(inference_url="https://wca_api_url")
        model_client.session.post = Mock(return_value=response)
        model_client.get_api_key = mock_api_key
        if mock_model_id:
            model_client.get_model_id = mock_model_id
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        return model_client

    def assert_test(
        self, model_client, expected_status_code, expected_exception, expected_log_message
    ):
        self.user.rh_user_has_seat = True
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(reverse("explanations"), self.payload, format="json")
                self.assertEqual(r.status_code, expected_status_code)
                if expected_exception() is not None:
                    self.assert_error_detail(
                        r, expected_exception().default_code, expected_exception().default_detail
                    )
                    self.assertInLog(expected_log_message, log)
                return r

    def test_bad_wca_request(self):
        model_client = self.stub_wca_client(
            400,
        )
        self.assert_test(
            model_client,
            HTTPStatus.NO_CONTENT,
            WcaBadRequestException,
            "WCA returned a bad request response.",
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
            "A WCA Api Key was expected but not found. Please contact your administrator.",
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
            "A WCA Model ID was expected but not found. Please contact your administrator.",
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
            "No default WCA Model ID was found.",
        )

    def test_request_id_correlation_failure(self):
        model_client = self.stub_wca_client(200)
        model_client.session.post = Mock(
            return_value=MockResponse(
                json={},
                status_code=200,
                headers={WCA_REQUEST_ID_HEADER: "some-other-uuid"},
            )
        )
        self.assert_test(
            model_client,
            HTTPStatus.INTERNAL_SERVER_ERROR,
            WcaRequestIdCorrelationFailureException,
            "WCA Request/Response Request Id correlation failed.",
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
            "WCA Model ID is invalid. Please contact your administrator.",
        )

    def test_empty_response(self):
        model_client = self.stub_wca_client(
            204,
        )
        self.assert_test(
            model_client,
            HTTPStatus.NO_CONTENT,
            WcaEmptyResponseException,
            "WCA returned an empty response.",
        )

    def test_cloudflare_rejection(self):
        model_client = self.stub_wca_client(403, response_text="cloudflare rejection")
        self.assert_test(
            model_client,
            HTTPStatus.BAD_REQUEST,
            WcaCloudflareRejectionException,
            "Cloudflare rejected the request. Please contact your administrator.",
        )

    def test_hap_filter(self):
        model_client = self.stub_wca_client(
            400,
            mock_model_id=Mock(return_value="garbage"),
            response_data={
                "detail": "our filters detected a potential problem with entities in your input"
            },
        )
        self.assert_test(
            model_client,
            HTTPStatus.BAD_REQUEST,
            WcaHAPFilterRejectionException,
            "WCA Hate, Abuse, and Profanity filter rejected the request.",
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
            "User trial expired. Please contact your administrator.",
        )

    def test_wca_instance_deleted(self):
        model_client = self.stub_wca_client(
            404,
            response_data={
                "detail": (
                    "Failed to get remaining capacity from Metering API: "
                    "The WCA instance 'banana' has been deleted."
                )
            },
        )
        self.assert_test(
            model_client,
            HTTPStatus.IM_A_TEAPOT,
            WcaInstanceDeletedException,
            "The WCA instance associated with the Model ID has been deleted."
            "Please contact your administrator.",
        )

    def test_wca_request_with_model_id_given(self):
        self.payload["model"] = "mymodel"
        model_client = self.stub_wca_client(
            200, mock_model_id=None, response_text=json.dumps({"explanation": "dummy explanation"})
        )
        model_client.invoke = lambda *args: {
            "content": "string",
            "format": "string",
            "explanationId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        }
        with self.assertLogs(
            logger="ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_saas", level="DEBUG"
        ) as log:
            self.assert_test(
                model_client,
                HTTPStatus.OK,
                lambda: None,
                None,
            )
            self.assertInLog("requested_model_id=mymodel", log)


@override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="dummy")
@override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
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
    def test_ok_with_model_id(self):
        generation_id = str(uuid.uuid4())
        model = "mymodel"
        payload = {
            "text": "Install nginx on RHEL9",
            "generationId": generation_id,
            "ansibleExtensionVersion": "24.4.0",
            "model": model,
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("generations"), payload, format="json")
            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertEqual(segment_events[0]["properties"]["modelName"], "mymodel")
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
        mocked_client.invoke.return_value = ("foo", "bar", [])
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=mocked_client),
        ):
            self.client.force_authenticate(user=self.user)
            self.client.post(reverse("generations"), payload, format="json")

        args: PlaybookGenerationParameters = mocked_client.invoke.call_args[0][0]
        self.assertFalse(args.create_outline)
        self.assertEqual(args.text, "Install nginx on RHEL9 isabella13@example.com")

    def test_unauthorized(self):
        generation_id = str(uuid.uuid4())
        payload = {
            "text": "Install nginx on RHEL9",
            "generationId": generation_id,
            "ansibleExtensionVersion": "24.4.0",
        }
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=MockedPipelinePlaybookGeneration(self.response_data)),
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
            "get_model_pipeline",
            Mock(return_value=MockedPipelinePlaybookGeneration(self.response_data)),
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
            "get_model_pipeline",
            Mock(return_value=MockedPipelinePlaybookGeneration(self.response_pii_data)),
        ):
            self.client.force_authenticate(user=self.user)
            r = self.client.post(reverse("generations"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertIsNotNone(r.data["playbook"])
            self.assertIsNotNone(r.data["outline"])
            self.assertFalse("admin@redhat.com" in r.data["playbook"])
            self.assertFalse("admin@redhat.com" in r.data["outline"])

    @patch(
        "ansible_ai_connect.ai.api.model_pipelines.dummy.pipelines."
        "DummyPlaybookGenerationPipeline.invoke"
    )
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

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    def test_with_custom_prompt_valid(self):
        payload = {
            "text": "Install nginx on RHEL9 jean-marc@redhat.com",
            "customPrompt": "You are an Ansible expert. Explain {goal} with {outline}.",
            "outline": "Install nginx. Start nginx.",
            "generationId": str(uuid.uuid4()),
            "ansibleExtensionVersion": "24.4.0",
        }
        mocked_client = Mock()
        mocked_client.invoke.return_value = ("foo", "bar", [])
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=mocked_client),
        ):
            self.client.force_authenticate(user=self.user)
            self.client.post(reverse("generations"), payload, format="json")

        args: PlaybookGenerationParameters = mocked_client.invoke.call_args[0][0]
        self.assertFalse(args.create_outline)
        self.assertEqual(args.outline, "Install nginx. Start nginx.")
        self.assertEqual(
            args.custom_prompt, "You are an Ansible expert. Explain {goal} with {outline}."
        )
        self.assertEqual(args.text, "Install nginx on RHEL9 isabella13@example.com")

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    def test_with_custom_prompt_blank(self):
        payload = {
            "text": "Install nginx on RHEL9 jean-marc@redhat.com",
            "customPrompt": "",
            "outline": "Install nginx. Start nginx.",
            "generationId": str(uuid.uuid4()),
            "ansibleExtensionVersion": "24.4.0",
        }
        mocked_client = Mock()
        mocked_client.generate_playbook.return_value = ("foo", "bar", [])
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=mocked_client),
        ):
            self.client.force_authenticate(user=self.user)
            r = self.client.post(reverse("generations"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assertFalse(mocked_client.generate_playbook.called)
            self.assertIn("detail", r.data)
            self.assertIn("customPrompt", r.data["detail"])
            self.assertIn(
                "This field may not be blank.",
                str(r.data["detail"]["customPrompt"]),
            )

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    def test_with_custom_prompt_missing_goal(self):
        payload = {
            "text": "Install nginx on RHEL9 jean-marc@redhat.com",
            "customPrompt": "You are an Ansible expert",
            "generationId": str(uuid.uuid4()),
            "ansibleExtensionVersion": "24.4.0",
        }
        mocked_client = Mock()
        mocked_client.generate_playbook.return_value = ("foo", "bar", [])
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=mocked_client),
        ):
            self.client.force_authenticate(user=self.user)
            r = self.client.post(reverse("generations"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assertFalse(mocked_client.generate_playbook.called)
            self.assertIn("detail", r.data)
            self.assertIn("customPrompt", r.data["detail"])
            self.assertIn("'{goal}' placeholder expected.", r.data["detail"]["customPrompt"])

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    def test_with_custom_prompt_missing_outline(self):
        payload = {
            "text": "Install nginx on RHEL9 jean-marc@redhat.com",
            "customPrompt": "You are an Ansible expert. Explain {goal}.",
            "outline": "Install nginx. Start nginx.",
            "generationId": str(uuid.uuid4()),
            "ansibleExtensionVersion": "24.4.0",
        }
        mocked_client = Mock()
        mocked_client.generate_playbook.return_value = ("foo", "bar", [])
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=mocked_client),
        ):
            self.client.force_authenticate(user=self.user)
            r = self.client.post(reverse("generations"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assertFalse(mocked_client.generate_playbook.called)
            self.assertIn("detail", r.data)
            self.assertIn("customPrompt", r.data["detail"])
            self.assertIn(
                "'{outline}' placeholder expected when 'outline' provided.",
                r.data["detail"]["customPrompt"],
            )

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    def test_with_custom_prompt_missing_outline_when_not_needed(self):
        payload = {
            "text": "Install nginx on RHEL9 jean-marc@redhat.com",
            "customPrompt": "You are an Ansible expert. Explain {goal}.",
            "generationId": str(uuid.uuid4()),
            "ansibleExtensionVersion": "24.4.0",
        }
        mocked_client = Mock()
        mocked_client.invoke.return_value = ("foo", "bar", [])
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=mocked_client),
        ):
            self.client.force_authenticate(user=self.user)
            self.client.post(reverse("generations"), payload, format="json")

        args: PlaybookGenerationParameters = mocked_client.invoke.call_args[0][0]
        self.assertFalse(args.create_outline)
        self.assertEqual(args.outline, "")
        self.assertEqual(args.custom_prompt, "You are an Ansible expert. Explain {goal}.")
        self.assertEqual(args.text, "Install nginx on RHEL9 isabella13@example.com")


@override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="dummy")
class TestRoleGenerationView(WisdomAppsBackendMocking, WisdomServiceAPITestCaseBase):
    def test_ok(self):
        payload = {}
        self.client.force_authenticate(user=self.user)
        r = self.client.post(reverse("generations/role"), payload, format="json")
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertIsNotNone(r.data)
        self.assertEqual(r.data, {})

    def test_unauthorized(self):
        payload = {}
        # Hit the API without authentication
        r = self.client.post(reverse("generations/role"), payload, format="json")
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)


@override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="wca")
@override_settings(ANSIBLE_AI_ENABLE_PLAYBOOK_ENDPOINT=True)
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
        model_client = WCASaaSPlaybookGenerationPipeline(inference_url="https://wca_api_url")
        model_client.session.post = Mock(return_value=response)
        model_client.get_api_key = mock_api_key
        if mock_model_id:
            model_client.get_model_id = mock_model_id
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        return model_client

    def assert_test(
        self, model_client, expected_status_code, expected_exception, expected_log_message
    ):
        self.user.rh_user_has_seat = True
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(reverse("generations"), self.payload, format="json")
                self.assertEqual(r.status_code, expected_status_code)
                if expected_exception() is not None:
                    self.assert_error_detail(
                        r, expected_exception().default_code, expected_exception().default_detail
                    )
                    self.assertInLog(expected_log_message, log)
                return r

    def test_bad_wca_request(self):
        model_client = self.stub_wca_client(
            400,
        )
        self.assert_test(
            model_client,
            HTTPStatus.NO_CONTENT,
            WcaBadRequestException,
            "bad request for playbook generation",
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
            "A WCA Api Key was expected but not found for playbook generation",
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
            "A WCA Model ID was expected but not found for playbook generation",
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
            "A default WCA Model ID was expected but not found for playbook generation",
        )

    def test_request_id_correlation_failure(self):
        model_client = self.stub_wca_client(200)
        model_client.session.post = Mock(
            return_value=MockResponse(
                json={},
                status_code=200,
                headers={WCA_REQUEST_ID_HEADER: "some-other-uuid"},
            )
        )
        self.assert_test(
            model_client,
            HTTPStatus.INTERNAL_SERVER_ERROR,
            WcaRequestIdCorrelationFailureException,
            "WCA Request/Response GenerationId correlation failed",
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
            "WCA Model ID is invalid for playbook generation",
        )

    def test_empty_response(self):
        model_client = self.stub_wca_client(
            204,
        )
        self.assert_test(
            model_client,
            HTTPStatus.NO_CONTENT,
            WcaEmptyResponseException,
            "WCA returned an empty response for playbook generation",
        )

    def test_cloudflare_rejection(self):
        model_client = self.stub_wca_client(403, response_text="cloudflare rejection")
        self.assert_test(
            model_client,
            HTTPStatus.BAD_REQUEST,
            WcaCloudflareRejectionException,
            "Cloudflare rejected the request for playbook generation",
        )

    def test_hap_filter(self):
        model_client = self.stub_wca_client(
            400,
            mock_model_id=Mock(return_value="garbage"),
            response_data={
                "detail": "our filters detected a potential problem with entities in your input"
            },
        )
        self.assert_test(
            model_client,
            HTTPStatus.BAD_REQUEST,
            WcaHAPFilterRejectionException,
            "WCA Hate, Abuse, and Profanity filter rejected the request for playbook generation",
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
            "User trial expired, when requesting playbook generation",
        )

    def test_wca_instance_deleted(self):
        model_client = self.stub_wca_client(
            404,
            response_data={
                "detail": (
                    "Failed to get remaining capacity from Metering API: "
                    "The WCA instance 'banana' has been deleted."
                )
            },
        )
        self.assert_test(
            model_client,
            HTTPStatus.IM_A_TEAPOT,
            WcaInstanceDeletedException,
            "WCA Instance has been deleted when requesting playbook generation",
        )

    def test_wca_request_with_model_id_given(self):
        self.payload["model"] = "mymodel"
        model_client = self.stub_wca_client(
            200,
            mock_model_id=None,
            response_text=json.dumps(
                {
                    "playbook": "- hosts: all",
                    "outline": "- dummy",
                    "warning": None,
                }
            ),
        )
        model_client.invoke = lambda *args: ("playbook", "outline", "warning")

        with self.assertLogs(
            logger="ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_saas", level="DEBUG"
        ) as log:
            self.assert_test(
                model_client,
                HTTPStatus.OK,
                lambda: None,
                None,
            )
            self.assertInLog("requested_model_id=mymodel", log)

    def test_warnings(self):
        model_client = self.stub_wca_client(
            200,
            mock_model_id=Mock(return_value="garbage"),
            response_text='{"playbook": "playbook", "outline": "outline", '
            '"warnings": [{"id": "id-1", "message": '
            '"Something went wrong", "details": "Some details"}]}',
        )
        r = self.assert_test(model_client, HTTPStatus.OK, lambda: None, None)
        self.assertTrue("warnings" in r.data)
        warnings = r.data["warnings"]
        self.assertEqual(1, len(warnings))
        self.assertEqual("id-1", warnings[0]["id"])
        self.assertEqual("Something went wrong", warnings[0]["message"])
        self.assertEqual("Some details", warnings[0]["details"])


@modify_settings()
@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
@override_settings(DEPLOYMENT_MODE="onprem")
@override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="wca-onprem")
@override_settings(ANSIBLE_WCA_USERNAME="bo")
@override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY="my-secret-key")
class TestExplanationFeatureEnableForWcaOnprem(
    WisdomAppsBackendMocking, WisdomServiceAPITestCaseBase
):

    explanation_id = str(uuid.uuid4())
    payload_json = {
        "content": "Install Wordpress on a RHEL9",
        "explanationId": explanation_id,
    }

    response_json = {"explanation": "dummy explanation"}

    def setUp(self):
        super().setUp()
        self.username = "u" + "".join(random.choices(string.digits, k=5))
        self.aap_user = create_user_with_provider(
            provider=USER_SOCIAL_AUTH_PROVIDER_AAP,
            rh_org_id=1981,
            social_auth_extra_data={"aap_licensed": True},
        )
        self.aap_user.save()

    def tearDown(self):
        Organization.objects.filter(id=1981).delete()
        self.aap_user.delete()
        super().tearDown()

    def stub_wca_client(self):
        response = MockResponse(
            json=self.response_json,
            text=json.dumps(self.response_json),
            status_code=HTTPStatus.OK,
        )
        model_client = WCASaaSPlaybookExplanationPipeline(inference_url="https://wca_api_url")
        model_client.session.post = Mock(return_value=response)
        model_client.get_api_key = Mock(return_value="org-api-key")
        model_client.get_model_id = Mock(return_value="model_id")
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        return model_client

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=False)
    @override_settings(ANSIBLE_AI_ENABLE_PLAYBOOK_ENDPOINT=False)
    def test_feature_not_enabled_yet(self):
        self.client.force_login(user=self.aap_user)
        r = self.client.post(reverse("explanations"), self.payload_json)
        self.assertEqual(r.status_code, 404)

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=False)
    @override_settings(ANSIBLE_AI_ENABLE_PLAYBOOK_ENDPOINT=True)
    def test_feature_enabled(self):
        self.client.force_authenticate(user=self.aap_user)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=self.stub_wca_client()),
        ):
            r = self.client.post(reverse("explanations"), self.payload_json, format="json")
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertEqual(r.data["content"], "dummy explanation")
            self.assertEqual(r.data["format"], "markdown")
            self.assertEqual(r.data["explanationId"], self.explanation_id)


@modify_settings()
@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
@override_settings(DEPLOYMENT_MODE="onprem")
@override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="wca-onprem")
@override_settings(ANSIBLE_WCA_USERNAME="bo")
@override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY="my-secret-key")
class TestGenerationFeatureEnableForWcaOnprem(
    WisdomAppsBackendMocking, WisdomServiceAPITestCaseBase
):
    generation_id = str(uuid.uuid4())
    payload_json = {
        "text": "Install nginx on RHEL9",
        "generationId": generation_id,
        "ansibleExtensionVersion": "24.4.0",
    }

    response_json = {
        "playbook": "- hosts: all",
        "outline": "- dummy",
        "warning": None,
    }

    def setUp(self):
        super().setUp()
        self.username = "u" + "".join(random.choices(string.digits, k=5))
        self.aap_user = create_user_with_provider(
            provider=USER_SOCIAL_AUTH_PROVIDER_AAP,
            rh_org_id=1981,
            social_auth_extra_data={"aap_licensed": True},
        )
        self.aap_user.save()

    def tearDown(self):
        Organization.objects.filter(id=1981).delete()
        self.aap_user.delete()
        super().tearDown()

    def stub_wca_client(self):
        response = MockResponse(
            json=self.response_json,
            text=json.dumps(self.response_json),
            status_code=HTTPStatus.OK,
        )
        model_client = WCASaaSPlaybookGenerationPipeline(inference_url="https://wca_api_url")
        model_client.session.post = Mock(return_value=response)
        model_client.get_api_key = Mock(return_value="org-api-key")
        model_client.get_model_id = Mock(return_value="model_id")
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        return model_client

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=False)
    @override_settings(ANSIBLE_AI_ENABLE_PLAYBOOK_ENDPOINT=False)
    def test_feature_not_enabled_yet(self):
        self.client.force_login(user=self.aap_user)
        r = self.client.post(reverse("generations"), self.payload_json, format="json")
        self.assertEqual(r.status_code, 404)

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=False)
    @override_settings(ANSIBLE_AI_ENABLE_PLAYBOOK_ENDPOINT=True)
    # GitHub Action 'Code Coverage' enables Lint'ing; so do the same (as it affects the response)
    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=True)
    def test_feature_enabled(self):
        self.client.force_authenticate(user=self.aap_user)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=self.stub_wca_client()),
        ):
            r = self.client.post(reverse("generations"), self.payload_json, format="json")
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertEqual(r.data["playbook"], "---\n- hosts: all\n")
            self.assertEqual(r.data["format"], "plaintext")
            self.assertEqual(r.data["generationId"], self.generation_id)


class TestChatView(WisdomServiceAPITestCaseBase):

    VALID_PAYLOAD = {
        "query": "Hello",
    }

    VALID_PAYLOAD_WITH_CONVERSATION_ID = {
        "query": "Hello",
        "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
    }

    INVALID_PAYLOAD = {
        "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
    }

    PAYLOAD_INVALID_RESPONSE = {
        "query": "Return an invalid response",
    }

    PAYLOAD_UNAUTHORIZERD = {
        "query": "Return the unauthorized status code",
    }

    PAYLOAD_FORBIDDEN = {
        "query": "Return the forbidden status code",
    }

    PAYLOAD_PROMPT_TOO_LONG = {
        "query": "Return the prompt too long status code",
    }

    PAYLOAD_PROMPT_VALIDATION_FAILED = {
        "query": "Return the validation failed status code",
    }

    PAYLOAD_INTERNAL_SERVER_ERROR = {
        "query": "Return the internal server error status code",
    }

    JSON_RESPONSE = {
        "response": "AAP 2.5 introduces an updated, unified UI.",
        "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
        "truncated": False,
        "referenced_documents": [],
    }

    @staticmethod
    def mocked_requests_post(*args, **kwargs):
        class MockResponse:
            def __init__(self, json_data, status_code):
                self.json_data = json_data
                self.status_code = status_code
                self.text = json.dumps(json_data)

            def json(self):
                return self.json_data

        # Make sure that the given json data is serializable
        json.dumps(kwargs["json"])

        json_response = {
            "response": "AAP 2.5 introduces an updated, unified UI.",
            "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
            "truncated": False,
            "referenced_documents": [],
        }
        status_code = 200

        if kwargs["json"]["query"] == TestChatView.PAYLOAD_INVALID_RESPONSE["query"]:
            json_response = {
                "response": "AAP 2.5 introduces an updated, unified UI.",
                # "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
                "truncated": False,
                "referenced_documents": [],
            }
        elif kwargs["json"]["query"] == TestChatView.PAYLOAD_UNAUTHORIZERD["query"]:
            status_code = 401
            json_response = {
                "detail": "Unauthorized",
            }
        elif kwargs["json"]["query"] == TestChatView.PAYLOAD_FORBIDDEN["query"]:
            status_code = 403
            json_response = {
                "detail": "Forbidden",
            }
        elif kwargs["json"]["query"] == TestChatView.PAYLOAD_PROMPT_TOO_LONG["query"]:
            status_code = 413
            json_response = {
                "detail": "Prompt too long",
            }
        elif kwargs["json"]["query"] == TestChatView.PAYLOAD_PROMPT_VALIDATION_FAILED["query"]:
            status_code = 422
            json_response = {
                "detail": "Validation failed",
            }
        elif kwargs["json"]["query"] == TestChatView.PAYLOAD_INTERNAL_SERVER_ERROR["query"]:
            status_code = 500
            json_response = {
                "detail": "Internal server error",
            }

        return MockResponse(json_response, status_code)

    @override_settings(CHATBOT_URL="http://localhost:8080")
    @override_settings(CHATBOT_DEFAULT_PROVIDER="wisdom")
    @override_settings(CHATBOT_DEFAULT_MODEL="granite-8b")
    @mock.patch(
        "requests.post",
        side_effect=mocked_requests_post,
    )
    def query_with_no_error(self, payload, mock_post):
        return self.client.post(reverse("chat"), payload, format="json")

    @mock.patch(
        "requests.post",
        side_effect=mocked_requests_post,
    )
    def query_without_chat_config(self, payload, mock_post):
        return self.client.post(reverse("chat"), payload, format="json")

    def assert_test(
        self, payload, expected_status_code=200, expected_exception=None, expected_log_message=None
    ):
        mocked_client = Mock()
        self.client.force_authenticate(user=self.user)
        with (
            patch.object(
                apps.get_app_config("ai"),
                "get_model_pipeline",
                Mock(return_value=mocked_client),
            ),
            self.assertLogs(logger="root", level="DEBUG") as log,
        ):
            self.client.force_authenticate(user=self.user)

            if expected_exception == ChatbotNotEnabledException:
                r = self.query_without_chat_config(payload)
            else:
                r = self.query_with_no_error(payload)

            self.assertEqual(r.status_code, expected_status_code)
            if expected_exception is not None:
                self.assert_error_detail(
                    r, expected_exception().default_code, expected_exception().default_detail
                )
                self.assertInLog(expected_log_message, log)

    def test_chat(self):
        self.assert_test(TestChatView.VALID_PAYLOAD)

    def test_chat_with_conversation_id(self):
        self.assert_test(TestChatView.VALID_PAYLOAD_WITH_CONVERSATION_ID)

    def test_chat_not_enabled_exception(self):
        self.assert_test(
            TestChatView.VALID_PAYLOAD, 503, ChatbotNotEnabledException, "Chatbot is not enabled"
        )

    def test_chat_invalid_request_exception(self):
        self.assert_test(
            TestChatView.INVALID_PAYLOAD,
            400,
            ChatbotInvalidRequestException,
            "ChatbotInvalidRequestException",
        )

    def test_chat_invalid_response_exception(self):
        self.assert_test(
            TestChatView.PAYLOAD_INVALID_RESPONSE,
            500,
            ChatbotInvalidResponseException,
            "ChatbotInvalidResponseException",
        )

    def test_chat_unauthorized_exception(self):
        self.assert_test(
            TestChatView.PAYLOAD_UNAUTHORIZERD,
            503,
            ChatbotUnauthorizedException,
            "ChatbotUnauthorizedException",
        )

    def test_chat_forbidden_exception(self):
        self.assert_test(
            TestChatView.PAYLOAD_FORBIDDEN,
            403,
            ChatbotForbiddenException,
            "ChatbotForbiddenException",
        )

    def test_chat_prompt_too_long_exception(self):
        self.assert_test(
            TestChatView.PAYLOAD_PROMPT_TOO_LONG,
            413,
            ChatbotPromptTooLongException,
            "ChatbotPromptTooLongException",
        )

    def test_chat_validation_exception(self):
        self.assert_test(
            TestChatView.PAYLOAD_PROMPT_VALIDATION_FAILED,
            422,
            ChatbotValidationException,
            "ChatbotValidationException",
        )

    def test_chat_internal_server_exception(self):
        self.assert_test(
            TestChatView.PAYLOAD_INTERNAL_SERVER_ERROR,
            500,
            ChatbotInternalServerException,
            "ChatbotInternalServerException",
        )
