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
import unittest
from http import HTTPStatus

from django.test import override_settings

from ansible_ai_connect.ai.api.model_pipelines.tests import mock_config
from ansible_ai_connect.test_utils import (
    APIVersionTestCaseBase,
    WisdomAppsBackendMocking,
    WisdomServiceAPITestCaseBaseOIDC,
)


@override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("dummy"))
@override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
class TestRoleExplanationViewDummy(
    APIVersionTestCaseBase, WisdomAppsBackendMocking, WisdomServiceAPITestCaseBaseOIDC
):
    def test_ok(self):
        payload = {
            "files": [
                {
                    "path": "dummy_path",
                    "content": "dummy_content",
                    "file_type": "dummy_file_type",
                }
            ],
            "roleName": "dummy_role",
        }
        self.start_user_plan()
        self.client.force_authenticate(user=self.user)
        r = self.client.post(self.api_version_reverse("explanations/role"), payload, format="json")
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertIsNotNone(r.data)
        self.assertEqual(r.data["format"], "markdown")

    def test_unauthorized(self):
        payload = {}
        # Hit the API without authentication
        r = self.client.post(self.api_version_reverse("explanations/role"), payload, format="json")
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)


@override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("wca"))
@override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
class TestRoleExplanationViewWCA(
    APIVersionTestCaseBase, WisdomAppsBackendMocking, WisdomServiceAPITestCaseBaseOIDC
):
    def test_ok(self):
        payload = {
            "files": [
                {
                    "path": "dummy_path",
                    "content": "dummy_content",
                    "file_type": "dummy_file_type",
                }
            ],
            "roleName": "dummy_role",
        }
        self.start_user_plan()
        self.client.force_authenticate(user=self.user)

        # with patch.object(ProductionClass, 'method', return_value=None) as mock_method:

        def m_post(url, *argv, **kwarg):
            m_resp = unittest.mock.Mock()
            if url.endswith("/token"):
                m_resp.json.return_value = {"access_token": "Café au lait"}
            elif url.endswith("/codegen/ansible/roles/explain"):
                m_resp.text = json.dumps(
                    {"explanation": "\n\n## Summary\nThe role installs the emacs package.\n"}
                )
            else:
                raise ValueError(f"unexpected API call: {url}")
            return m_resp

        mocked_session = unittest.mock.Mock()
        mocked_session.post = m_post

        def MockedSession():
            return mocked_session

        with unittest.mock.patch(
            "ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base.requests.Session",
            MockedSession,
        ):
            r = self.client.post(
                self.api_version_reverse("explanations/role"), payload, format="json"
            )
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertIsNotNone(r.data)
        self.assertEqual(r.data["format"], "markdown")
        self.assertIn("emacs", r.data["content"])
