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
import logging
import uuid
from http import HTTPStatus
from typing import Optional
from unittest.mock import Mock, patch

from django.apps import apps
from django.test import override_settings

from ansible_ai_connect.ai.api.model_pipelines.config_pipelines import BaseConfig
from ansible_ai_connect.ai.api.model_pipelines.dummy.pipelines import ROLE_FILES
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    ModelPipelineRoleGeneration,
    RoleGenerationParameters,
    RoleGenerationResponse,
)
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_config
from ansible_ai_connect.healthcheck.backends import HealthCheckSummary
from ansible_ai_connect.test_utils import (
    APIVersionTestCaseBase,
    WisdomAppsBackendMocking,
    WisdomServiceAPITestCaseBase,
)

logger = logging.getLogger(__name__)


class MockedConfig(BaseConfig):
    def __init__(self):
        super().__init__(inference_url="mock-url", model_id="mock-model", timeout=None)


class MockedPipelineRoleGeneration(ModelPipelineRoleGeneration[MockedConfig]):

    def __init__(
        self,
        response_roles: str,
        response_files: list,
        response_outline: str,
        response_warnings: list,
    ):
        super().__init__(MockedConfig())
        self.response_roles = response_roles
        self.response_files = response_files
        self.response_outline = response_outline
        self.response_warnings = response_warnings

    def invoke(self, params: RoleGenerationParameters) -> RoleGenerationResponse:
        return (
            self.response_roles,
            self.response_files,
            self.response_outline,
            self.response_warnings,
        )

    def self_test(self) -> Optional[HealthCheckSummary]:
        raise NotImplementedError


@override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("dummy"))
class TestRoleGenerationView(
    APIVersionTestCaseBase, WisdomAppsBackendMocking, WisdomServiceAPITestCaseBase
):

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_ok(self):
        generation_id = uuid.uuid4()
        payload = {
            "text": "Set up MySQL and email the admin",
            "generationId": generation_id,
            "ansibleExtensionVersion": "24.4.0",
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(
                self.api_version_reverse("generations/role"), payload, format="json"
            )
            segment_events = self.extractSegmentEventsFromLog(log)
            roleGenEvent = segment_events[0]
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertIsNotNone(r.data)
        self.assertEqual(r.data["files"], ROLE_FILES)
        self.assertEqual(r.data["format"], "plaintext")
        self.assertEqual(r.data["generationId"], generation_id)
        self.assertEqual(r.data["outline"], "")
        self.assertEqual(r.data["role"], "install_nginx")
        self.assertEqual(roleGenEvent["event"], "codegenRole")
        self.assertEqual(roleGenEvent["properties"]["generationId"], str(generation_id))

    def test_unauthorized(self):
        payload = {}
        # Hit the API without authentication
        r = self.client.post(self.api_version_reverse("generations/role"), payload, format="json")
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    def test_with_anonymized_response(self):
        generation_id = str(uuid.uuid4())
        payload = {
            "text": "Install mysql and email admin@redhat.com",
            "generationId": generation_id,
            "ansibleExtensionVersion": "24.4.0",
        }

        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(
                return_value=MockedPipelineRoleGeneration(
                    "Install mysql and email admin@redhat.com",
                    [
                        {
                            "name": "main.yml",
                            "content": """
                      ---
                        - name: Install MySQL
                            package:
                                name: mysql
                                state: present
                        - name: Email admin
                            mail:
                                to: admin@redhat.com
                      """,
                        }
                    ],
                    "Install mysql and email admin@redhat.com",
                    [],
                )
            ),
        ):
            self.client.force_authenticate(user=self.user)
            r = self.client.post(
                self.api_version_reverse("generations/role"), payload, format="json"
            )
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertIsNotNone(r.data["role"])
            self.assertEqual(len(r.data["files"]), 1)
            self.assertIsNotNone(r.data["outline"])
            self.assertTrue("mysql" in r.data["role"])
            self.assertTrue("mysql" in r.data["outline"])
            self.assertFalse("admin@redhat.com" in r.data["role"])
            self.assertFalse("admin@redhat.com" in r.data["outline"])
            for file in r.data["files"]:
                self.assertFalse("admin@redhat.com" in file["content"])
