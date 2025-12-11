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
import time
import uuid
from http import HTTPStatus
from typing import Optional, Union
from unittest.mock import Mock, patch

import requests
from django.apps import apps
from django.test import modify_settings, override_settings
from rest_framework.exceptions import APIException

from ansible_ai_connect.ai.api.data.data_model import APIPayload
from ansible_ai_connect.ai.api.exceptions import (
    FeatureNotAvailable,
    PostprocessException,
    PreprocessInvalidYamlException,
)
from ansible_ai_connect.ai.api.model_pipelines.config_pipelines import BaseConfig
from ansible_ai_connect.ai.api.model_pipelines.exceptions import (
    ModelTimeoutError,
    WcaBadRequest,
    WcaEmptyResponse,
    WcaException,
    WcaInvalidModelId,
    WcaKeyNotFound,
    WcaModelIdNotFound,
    WcaNoDefaultModelId,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    CompletionsParameters,
    CompletionsResponse,
    ModelPipelineCompletions,
)
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_pipeline_config
from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_saas import (
    WCASaaSCompletionsPipeline,
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
from ansible_ai_connect.healthcheck.backends import HealthCheckSummary
from ansible_ai_connect.test_utils import (
    APIVersionTestCaseBase,
    WisdomServiceAPITestCaseBase,
)
from ansible_ai_connect.users.models import User

logger = logging.getLogger(__name__)


class MockedConfig(BaseConfig):
    def __init__(self):
        super().__init__(inference_url="mock-url", model_id="mock-model", timeout=None)


class MockedPipelineCompletions(ModelPipelineCompletions[MockedConfig]):

    def __init__(
        self,
        test,
        payload,
        response_data,
        test_inference_match=True,
        rh_user_has_seat=False,
    ):
        super().__init__(MockedConfig())
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

    def infer_from_parameters(self, model_id, context, prompt, suggestion_id=None, headers=None):
        raise NotImplementedError

    def self_test(self) -> Optional[HealthCheckSummary]:
        raise NotImplementedError


@modify_settings()
class TestCompletionView(APIVersionTestCaseBase, WisdomServiceAPITestCaseBase):
    # An artificial model ID for model-ID related test cases.
    DUMMY_MODEL_ID = "01234567-1234-5678-9abc-0123456789ab<|sepofid|>wisdom_codegen"

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    def test_full_payload(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": "a-model-id",
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=MockedPipelineCompletions(self, payload, response_data)),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("completions"), payload)
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
            "model_id": "a-model-id",
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
                r = self.client.post(self.api_version_reverse("completions"), payload)
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
            "model_id": "a-model-id",
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
                r = self.client.post(self.api_version_reverse("completions"), payload)
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
            "model_id": "a-model-id",
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=MockedPipelineCompletions(self, payload, response_data)),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data["predictions"])
                for _ in range(10):
                    r = self.client.post(self.api_version_reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.TOO_MANY_REQUESTS)
                self.assertSegmentTimestamp(log)

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    def test_missing_prompt(self):
        payload = {
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": "a-model-id",
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=MockedPipelineCompletions(self, payload, response_data)),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
                self.assertSegmentTimestamp(log)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_authentication_error(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": "a-model-id",
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        # self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=MockedPipelineCompletions(self, payload, response_data)),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("completions"), payload)
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
            "model_id": "a-model-id",
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=MockedPipelineCompletions(self, payload, response_data)),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("completions"), payload)
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
            "model_id": "a-model-id",
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=MockedPipelineCompletions(self, payload, response_data)),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
                self.assertInLog("failed to validate request", log)
                self.assertTrue("prompt does not contain the name parameter" in str(r.content))
                self.assertSegmentTimestamp(log)

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    def test_full_payload_basic(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": "a-model-id",
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=MockedPipelineCompletions(self, payload, response_data)),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data["predictions"])
                self.assertSegmentTimestamp(log)

    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=False)
    def test_full_payload_without_ansible_lint_with_commercial_user(self):
        self.user.rh_user_has_seat = True
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "model_id": "a-model-id",
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
                r = self.client.post(self.api_version_reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data["predictions"])
                self.assertSegmentTimestamp(log)

    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=True)
    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_full_payload_with_ansible_lint_postprocess_with_commercial_user(self):
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
                r = self.client.post(self.api_version_reverse("completions"), payload)
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
            (FeatureNotAvailable(), HTTPStatus.NOT_FOUND),
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
            Mock(return_value=WCASaaSCompletionsPipeline(mock_pipeline_config("wca"))),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("completions"), payload)
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
                r = self.client.post(self.api_version_reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data["predictions"])
                self.assertIsNotNone(r.data["model"])
                self.assertIsNotNone(r.data["suggestionId"])
                self.assertSegmentTimestamp(log)
