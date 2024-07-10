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

import importlib
import os
from unittest.mock import patch

import django.conf
from django.test import SimpleTestCase
from oauth2_provider.settings import oauth2_settings

import ansible_ai_connect.main.settings.base
from ansible_ai_connect.test_utils import WisdomLogAwareMixin


class TestSettings(SimpleTestCase, WisdomLogAwareMixin):
    @classmethod
    def reload_settings(cls):
        module_name = os.getenv("DJANGO_SETTINGS_MODULE")
        settings_module = importlib.import_module(
            module_name.replace("ansible_wisdom.", "ansible_ai_connect.")
        )

        importlib.reload(ansible_ai_connect.main.settings.base)
        importlib.reload(settings_module)
        importlib.reload(django.conf)
        from django.conf import settings

        settings.configure(default_settings=settings_module)
        return settings

    @classmethod
    def tearDownClass(cls):
        cls.reload_settings()

    def test_oauth2(self):
        REFRESH_TOKEN_EXPIRE_SECONDS = oauth2_settings.REFRESH_TOKEN_EXPIRE_SECONDS
        self.assertGreater(REFRESH_TOKEN_EXPIRE_SECONDS, 0)
        self.assertLessEqual(REFRESH_TOKEN_EXPIRE_SECONDS, 864_000)

    @patch.dict(
        os.environ,
        {
            "ANSIBLE_AI_ENABLE_TECH_PREVIEW": "true",
            "SOCIAL_AUTH_GITHUB_TEAM_KEY": "teamkey",
            "SOCIAL_AUTH_GITHUB_TEAM_SECRET": "teamsecret",
            "SOCIAL_AUTH_GITHUB_TEAM_ID": "5678",
        },
    )
    def test_github_auth_team_with_id(self):
        settings = self.reload_settings()

        self.assertEqual(settings.USE_GITHUB_TEAM, True)
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_TEAM_KEY, "teamkey")
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_TEAM_SECRET, "teamsecret")
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_TEAM_ID, "5678")
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_TEAM_SCOPE, ["read:org"])
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_TEAM_EXTRA_DATA, ["login"])

    @patch.dict(
        os.environ,
        {
            "ANSIBLE_AI_ENABLE_TECH_PREVIEW": "true",
            "SOCIAL_AUTH_GITHUB_TEAM_KEY": "teamkey",
            "SOCIAL_AUTH_GITHUB_TEAM_SECRET": "teamsecret",
            "SOCIAL_AUTH_GITHUB_TEAM_ID": "",
        },
    )
    def test_github_auth_team_without_id(self):
        settings = self.reload_settings()
        self.assertEqual(settings.USE_GITHUB_TEAM, True)
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_TEAM_KEY, "teamkey")
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_TEAM_SECRET, "teamsecret")
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_TEAM_ID, 7188893)
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_TEAM_SCOPE, ["read:org"])
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_TEAM_EXTRA_DATA, ["login"])

    @patch.dict(
        os.environ,
        {
            "ANSIBLE_AI_ENABLE_TECH_PREVIEW": "true",
            "SOCIAL_AUTH_GITHUB_TEAM_KEY": "",
            "SOCIAL_AUTH_GITHUB_KEY": "key",
            "SOCIAL_AUTH_GITHUB_SECRET": "secret",
        },
    )
    def test_github_auth_team_empty_key(self):
        settings = self.reload_settings()
        self.assertEqual(settings.USE_GITHUB_TEAM, False)
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_KEY, "key")
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_SECRET, "secret")
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_SCOPE, [""])
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_EXTRA_DATA, ["login"])

    @patch.dict(
        os.environ,
        {
            "ANSIBLE_AI_MODEL_MESH_MODEL_NAME": "a-model",
        },
    )
    def test_use_of_model_mesh_model_name(self):
        with self.assertLogs(logger="root", level="DEBUG") as log:
            settings = self.reload_settings()
            self.assertEqual(settings.ANSIBLE_AI_MODEL_MESH_MODEL_ID, "a-model")
            self.assertTrue(
                self.searchInLogOutput("Use of ANSIBLE_AI_MODEL_MESH_MODEL_NAME is deprecated", log)
            )
            self.assertTrue(
                self.searchInLogOutput("Setting the value of ANSIBLE_AI_MODEL_MESH_MODEL_ID", log)
            )

    @patch.dict(
        os.environ,
        {
            "ANSIBLE_AI_MODEL_MESH_MODEL_NAME": "a-model",
            "ANSIBLE_AI_MODEL_MESH_MODEL_ID": "b-model",
        },
    )
    def test_use_of_model_mesh_model_name_and_model_id(self):
        with self.assertLogs(logger="root", level="DEBUG") as log:
            settings = self.reload_settings()
            self.assertEqual(settings.ANSIBLE_AI_MODEL_MESH_MODEL_ID, "b-model")
            self.assertTrue(
                self.searchInLogOutput("Use of ANSIBLE_AI_MODEL_MESH_MODEL_NAME is deprecated", log)
            )
            self.assertTrue(
                self.searchInLogOutput(
                    "ANSIBLE_AI_MODEL_MESH_MODEL_ID is set and will take precedence", log
                )
            )

    def test_ansible_ai_model_mesh_model_id_has_no_default(self):
        settings = self.reload_settings()
        self.assertIsNone(settings.ANSIBLE_AI_MODEL_MESH_MODEL_ID)
