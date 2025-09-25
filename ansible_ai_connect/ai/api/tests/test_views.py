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
import random
import string
import time
import uuid
from http import HTTPStatus
from typing import Optional, Union
from unittest.mock import Mock, patch

from django.apps import apps
from django.test import modify_settings, override_settings
from rest_framework.exceptions import APIException

from ansible_ai_connect.ai.api.data.data_model import APIPayload
from ansible_ai_connect.ai.api.exceptions import (
    ModelTimeoutException,
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
from ansible_ai_connect.ai.api.model_pipelines.config_pipelines import BaseConfig
from ansible_ai_connect.ai.api.model_pipelines.exceptions import (
    ModelTimeoutError,
    WcaBadRequest,
    WcaKeyNotFound,
    WcaModelIdNotFound,
    WcaNoDefaultModelId,
    WcaUserTrialExpired,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    CompletionsParameters,
    CompletionsResponse,
    ModelPipelineCompletions,
    ModelPipelinePlaybookGeneration,
    ModelPipelineRoleExplanation,
    PlaybookGenerationParameters,
    PlaybookGenerationResponse,
    RoleExplanationParameters,
    RoleExplanationResponse,
)
from ansible_ai_connect.ai.api.model_pipelines.tests import (
    mock_config,
    mock_pipeline_config,
)
from ansible_ai_connect.ai.api.model_pipelines.tests.test_wca_client import (
    WCA_REQUEST_ID_HEADER,
    MockResponse,
)
from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_onprem import (
    WCAOnPremPlaybookExplanationPipeline,
    WCAOnPremPlaybookGenerationPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_saas import (
    WCASaaSContentMatchPipeline,
    WCASaaSPlaybookExplanationPipeline,
    WCASaaSPlaybookGenerationPipeline,
)
from ansible_ai_connect.ai.api.pipelines.completion_context import CompletionContext
from ansible_ai_connect.ai.api.pipelines.completion_stages.pre_process import (
    completion_pre_process,
)
from ansible_ai_connect.ai.api.serializers import CompletionRequestSerializer
from ansible_ai_connect.healthcheck.backends import HealthCheckSummary
from ansible_ai_connect.main.tests.test_views import create_user_with_provider
from ansible_ai_connect.organizations.models import ExternalOrganization
from ansible_ai_connect.test_utils import (
    APIVersionTestCaseBase,
    WisdomAppsBackendMocking,
    WisdomLogAwareMixin,
    WisdomServiceAPITestCaseBase,
)
from ansible_ai_connect.users.constants import USER_SOCIAL_AUTH_PROVIDER_AAP
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


class MockedPipelinePlaybookGeneration(ModelPipelinePlaybookGeneration[MockedConfig]):

    def __init__(self, response_data):
        super().__init__(MockedConfig())
        self.response_data = response_data

    def invoke(self, params: PlaybookGenerationParameters) -> PlaybookGenerationResponse:
        return self.response_data, self.response_data, []

    def self_test(self) -> Optional[HealthCheckSummary]:
        raise NotImplementedError


class MockedPipelineRoleExplanation(ModelPipelineRoleExplanation[MockedConfig]):

    def __init__(self, response_data):
        super().__init__(MockedConfig())
        self.response_data = response_data

    def invoke(self, params: RoleExplanationParameters) -> RoleExplanationResponse:
        return self.response_data

    def self_test(self) -> Optional[HealthCheckSummary]:
        raise NotImplementedError


class TestContentMatchesWCAView(
    APIVersionTestCaseBase, WisdomAppsBackendMocking, WisdomServiceAPITestCaseBase
):
    def test_wca_contentmatch_single_task(self):
        self.user.rh_user_has_seat = True
        self.user.organization = ExternalOrganization.objects.get_or_create(id=1)[0]
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
        model_client = WCASaaSContentMatchPipeline(mock_pipeline_config("wca"))
        model_client.session.post = Mock(return_value=response)
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        model_client.get_api_key = Mock(return_value="org-api-key")
        model_client.get_model_id = Mock(return_value="org-model-id")
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            r = self.client.post(self.api_version_reverse("contentmatches"), payload)
            self.assertEqual(r.status_code, HTTPStatus.OK)

        model_client.get_token.assert_called_once()
        self.assertEqual(
            model_client.session.post.call_args.args[0],
            "http://localhost/v1/wca/codematch/ansible",
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
        self.user.organization = ExternalOrganization.objects.get_or_create(id=1)[0]
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
        model_client = WCASaaSContentMatchPipeline(mock_pipeline_config("wca"))
        model_client.session.post = Mock(return_value=response)
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        model_client.get_api_key = Mock(return_value="org-api-key")
        model_client.get_model_id = Mock(return_value="org-model-id")
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            r = self.client.post(self.api_version_reverse("contentmatches"), payload)
            self.assertEqual(r.status_code, HTTPStatus.OK)

        model_client.get_token.assert_called_once()
        self.assertEqual(
            model_client.session.post.call_args.args[0],
            "http://localhost/v1/wca/codematch/ansible",
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
        self.user.organization = ExternalOrganization.objects.get_or_create(id=1)[0]
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
        model_client = WCASaaSContentMatchPipeline(mock_pipeline_config("wca"))
        model_client.session.post = Mock(return_value=response)
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        model_client.get_api_key = Mock(return_value="org-api-key")
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            r = self.client.post(self.api_version_reverse("contentmatches"), payload)
            self.assertEqual(r.status_code, HTTPStatus.OK)

        model_client.get_token.assert_called_once()
        self.assertEqual(
            model_client.session.post.call_args.args[0],
            "http://localhost/v1/wca/codematch/ansible",
        )
        self.assertEqual(
            model_client.session.post.call_args.kwargs["json"]["model_id"], "org-model-id"
        )

    def test_wca_contentmatch_without_custom_model_id(self):
        self.user.rh_user_has_seat = True
        self.user.organization = ExternalOrganization.objects.get_or_create(id=1)[0]
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
        model_client = WCASaaSContentMatchPipeline(mock_pipeline_config("wca"))
        model_client.session.post = Mock(return_value=response)
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        model_client.get_api_key = Mock(return_value="org-api-key")
        model_client.get_model_id = Mock(return_value="org-model-id")
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            r = self.client.post(self.api_version_reverse("contentmatches"), payload)
            self.assertEqual(r.status_code, HTTPStatus.OK)

        model_client.get_token.assert_called_once()
        self.assertEqual(
            model_client.session.post.call_args.args[0],
            "http://localhost/v1/wca/codematch/ansible",
        )
        self.assertEqual(
            model_client.session.post.call_args.kwargs["json"]["model_id"], "org-model-id"
        )


class TestContentMatchesWCAViewErrors(
    APIVersionTestCaseBase,
    WisdomAppsBackendMocking,
    WisdomServiceAPITestCaseBase,
    WisdomLogAwareMixin,
):
    def setUp(self):
        super().setUp()

        self.user.rh_user_has_seat = True
        self.user.organization = ExternalOrganization.objects.get_or_create(id=1)[0]
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
        self.model_client = WCASaaSContentMatchPipeline(mock_pipeline_config("wca"))
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
                r = self.client.post(self.api_version_reverse("contentmatches"), self.payload)
                self.assertEqual(r.status_code, exception.status_code)
            self.assertInLog(str(exception.__name__), log)

        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=self.model_client),
        ):
            r = self.client.post(self.api_version_reverse("contentmatches"), self.payload)
            self.assert_error_detail(r, exception().default_code, exception().default_detail)

    def _assert_model_id_in_exception(self, expected_model_id):
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=self.model_client),
        ):
            r = self.client.post(self.api_version_reverse("contentmatches"), self.payload)
            self.assertEqual(r.data["model"], expected_model_id)


class TestContentMatchesWCAViewSegmentEvents(
    APIVersionTestCaseBase, WisdomAppsBackendMocking, WisdomServiceAPITestCaseBase
):
    def setUp(self):
        super().setUp()

        self.user.rh_user_has_seat = True
        self.user.organization = ExternalOrganization.objects.get_or_create(id=1)[0]
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

        self.model_client = WCASaaSContentMatchPipeline(mock_pipeline_config("wca"))
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
            r = self.client.post(self.api_version_reverse("contentmatches"), self.payload)
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
            r = self.client.post(self.api_version_reverse("contentmatches"), self.payload)
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
                r = self.client.post(self.api_version_reverse("contentmatches"), self.payload)
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
                r = self.client.post(self.api_version_reverse("contentmatches"), self.payload)
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


@override_settings(ANSIBLE_AI_ENABLE_PLAYBOOK_ENDPOINT=True)
class TestExplanationViewWithWCA(
    APIVersionTestCaseBase, WisdomAppsBackendMocking, WisdomServiceAPITestCaseBase
):

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
        model_client = WCASaaSPlaybookExplanationPipeline(mock_pipeline_config("wca"))
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
                r = self.client.post(
                    self.api_version_reverse("explanations"), self.payload, format="json"
                )
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


@override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("dummy"))
@override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
class TestGenerationView(
    APIVersionTestCaseBase, WisdomAppsBackendMocking, WisdomServiceAPITestCaseBase
):

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
        generation_id = uuid.uuid4()
        payload = {
            "text": "Install nginx on RHEL9",
            "generationId": generation_id,
            "ansibleExtensionVersion": "24.4.0",
        }
        self.client.force_authenticate(user=self.user)
        r = self.client.post(
            self.api_version_reverse("generations/playbook"), payload, format="json"
        )
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertIsNotNone(r.data["playbook"])
        self.assertEqual(r.data["format"], "plaintext")
        self.assertEqual(r.data["generationId"], generation_id)

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    def test_ok_with_model_id(self):
        generation_id = uuid.uuid4()
        model = "mymodel"
        payload = {
            "text": "Install nginx on RHEL9",
            "generationId": generation_id,
            "ansibleExtensionVersion": "24.4.0",
            "model": model,
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(
                self.api_version_reverse("generations/playbook"), payload, format="json"
            )
            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertEqual(segment_events[0]["properties"]["modelName"], "mymodel")
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertIsNotNone(r.data["playbook"])
        self.assertEqual(r.data["format"], "plaintext")
        self.assertEqual(r.data["generationId"], generation_id)

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
            r = self.client.post(
                self.api_version_reverse("generations/playbook"), payload, format="json"
            )
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
            r = self.client.post(
                self.api_version_reverse("generations/playbook"), payload, format="json"
            )
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
            r = self.client.post(
                self.api_version_reverse("generations/playbook"), payload, format="json"
            )
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
            r = self.client.post(
                self.api_version_reverse("generations/playbook"), payload, format="json"
            )
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
            self.client.post(
                self.api_version_reverse("generations/playbook"), payload, format="json"
            )

        args: PlaybookGenerationParameters = mocked_client.invoke.call_args[0][0]
        self.assertFalse(args.create_outline)
        self.assertEqual(args.outline, "Install nginx. Start nginx.")
        self.assertEqual(
            args.custom_prompt, "You are an Ansible expert. Explain {goal} with {outline}."
        )

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
            r = self.client.post(
                self.api_version_reverse("generations/playbook"), payload, format="json"
            )
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
            r = self.client.post(
                self.api_version_reverse("generations/playbook"), payload, format="json"
            )
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
            r = self.client.post(
                self.api_version_reverse("generations/playbook"), payload, format="json"
            )
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
            self.client.post(
                self.api_version_reverse("generations/playbook"), payload, format="json"
            )

        args: PlaybookGenerationParameters = mocked_client.invoke.call_args[0][0]
        self.assertFalse(args.create_outline)
        self.assertEqual(args.outline, "")
        self.assertEqual(args.custom_prompt, "You are an Ansible expert. Explain {goal}.")


@override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("wca"))
@override_settings(ANSIBLE_AI_ENABLE_PLAYBOOK_ENDPOINT=True)
class TestGenerationViewWithWCA(
    APIVersionTestCaseBase, WisdomAppsBackendMocking, WisdomServiceAPITestCaseBase
):

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
        model_client = WCASaaSPlaybookGenerationPipeline(mock_pipeline_config("wca"))
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
                r = self.client.post(
                    self.api_version_reverse("generations/playbook"), self.payload, format="json"
                )
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
            "WCA returned a bad request response",
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
            "WCA Request/Response Request Id correlation failed",
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
            "WCA Hate, Abuse, and Profanity filter rejected the request",
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
            "The WCA instance associated with the Model ID has been deleted",
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
@override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("wca-onprem"))
@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
@override_settings(DEPLOYMENT_MODE="onprem")
class TestExplanationFeatureEnableForWcaOnprem(
    APIVersionTestCaseBase, WisdomAppsBackendMocking, WisdomServiceAPITestCaseBase
):

    explanation_id = uuid.uuid4()
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
        ExternalOrganization.objects.filter(id=1981).delete()
        self.aap_user.delete()
        super().tearDown()

    def stub_wca_client(self):
        response = MockResponse(
            json=self.response_json,
            text=json.dumps(self.response_json),
            status_code=HTTPStatus.OK,
        )
        model_client = WCAOnPremPlaybookExplanationPipeline(mock_pipeline_config("wca-onprem"))
        model_client.session.post = Mock(return_value=response)
        model_client.get_api_key = Mock(return_value="org-api-key")
        model_client.get_model_id = Mock(return_value="model_id")
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        return model_client

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=False)
    @override_settings(ANSIBLE_AI_ENABLE_PLAYBOOK_ENDPOINT=False)
    def test_feature_not_enabled_yet(self):
        self.client.force_login(user=self.aap_user)
        r = self.client.post(self.api_version_reverse("explanations"), self.payload_json)
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
            r = self.client.post(
                self.api_version_reverse("explanations"), self.payload_json, format="json"
            )
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertEqual(r.data["content"], "dummy explanation")
            self.assertEqual(r.data["format"], "markdown")
            self.assertEqual(r.data["explanationId"], self.explanation_id)


@modify_settings()
@override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("wca-onprem"))
@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
@override_settings(DEPLOYMENT_MODE="onprem")
class TestGenerationFeatureEnableForWcaOnprem(
    APIVersionTestCaseBase, WisdomAppsBackendMocking, WisdomServiceAPITestCaseBase
):
    generation_id = uuid.uuid4()
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
        ExternalOrganization.objects.filter(id=1981).delete()
        self.aap_user.delete()
        super().tearDown()

    def stub_wca_client(self):
        response = MockResponse(
            json=self.response_json,
            text=json.dumps(self.response_json),
            status_code=HTTPStatus.OK,
        )
        model_client = WCAOnPremPlaybookGenerationPipeline(mock_pipeline_config("wca-onprem"))
        model_client.session.post = Mock(return_value=response)
        model_client.get_api_key = Mock(return_value="org-api-key")
        model_client.get_model_id = Mock(return_value="model_id")
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        return model_client

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=False)
    @override_settings(ANSIBLE_AI_ENABLE_PLAYBOOK_ENDPOINT=False)
    def test_feature_not_enabled_yet(self):
        self.client.force_login(user=self.aap_user)
        r = self.client.post(
            self.api_version_reverse("generations/playbook"), self.payload_json, format="json"
        )
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
            r = self.client.post(
                self.api_version_reverse("generations/playbook"), self.payload_json, format="json"
            )
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertEqual(r.data["playbook"], "---\n- hosts: all\n")
            self.assertEqual(r.data["format"], "plaintext")
            self.assertEqual(r.data["generationId"], self.generation_id)
