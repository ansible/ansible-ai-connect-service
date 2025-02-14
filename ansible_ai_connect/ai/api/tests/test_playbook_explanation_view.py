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
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    ModelPipelinePlaybookExplanation,
    PlaybookExplanationParameters,
    PlaybookExplanationResponse,
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


class MockedPipelinePlaybookExplanation(ModelPipelinePlaybookExplanation[MockedConfig]):

    def __init__(self, response_data):
        super().__init__(MockedConfig())
        self.response_data = response_data

    def invoke(self, params: PlaybookExplanationParameters) -> PlaybookExplanationResponse:
        return self.response_data

    def self_test(self) -> Optional[HealthCheckSummary]:
        raise NotImplementedError


@override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
@override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("dummy"))
@override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
class TestPlaybookExplanationView(
    APIVersionTestCaseBase, WisdomAppsBackendMocking, WisdomServiceAPITestCaseBase
):
    response_data = """# Information
This playbook installs the Nginx web server on all hosts
that are running Red Hat Enterprise Linux 9.
"""
    response_pii_data = """# Information
This playbook emails admin@redhat.com with a list of passwords.
"""

    def test_ok(self):
        explanation_id = uuid.uuid4()
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
            r = self.client.post(self.api_version_reverse("explanations"), payload, format="json")
            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertEqual(segment_events[0]["properties"]["playbook_length"], 165)
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertIsNotNone(r.data["content"])
        self.assertEqual(r.data["format"], "markdown")
        self.assertEqual(r.data["explanationId"], explanation_id)

    def test_ok_with_model_id(self):
        explanation_id = uuid.uuid4()
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
            r = self.client.post(self.api_version_reverse("explanations"), payload, format="json")
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
            self.client.post(self.api_version_reverse("explanations"), payload, format="json")

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
            r = self.client.post(self.api_version_reverse("explanations"), payload, format="json")
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
            r = self.client.post(self.api_version_reverse("explanations"), payload, format="json")
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
            r = self.client.post(self.api_version_reverse("explanations"), payload, format="json")
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
            r = self.client.post(self.api_version_reverse("explanations"), payload, format="json")
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
            self.client.post(self.api_version_reverse("explanations"), payload, format="json")

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
            r = self.client.post(self.api_version_reverse("explanations"), payload, format="json")
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
            r = self.client.post(self.api_version_reverse("explanations"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assertFalse(mocked_client.explain_playbook.called)
            self.assertIn("detail", r.data)
            self.assertIn("customPrompt", r.data["detail"])
            self.assertIn("'{playbook}' placeholder expected.", r.data["detail"]["customPrompt"])
