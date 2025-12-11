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
import json
import os
from unittest.mock import patch

import django.conf
from django.test import SimpleTestCase

import ansible_ai_connect.main.settings.base
from ansible_ai_connect.ai.api.model_pipelines.config_loader import load_config_from_str
from ansible_ai_connect.test_utils import WisdomLogAwareMixin


class TestLegacySettings(SimpleTestCase, WisdomLogAwareMixin):
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

    def test_model_service_sections(self):
        settings = self.reload_settings()
        config = json.loads(settings.ANSIBLE_AI_MODEL_MESH_CONFIG)

        # Lazy import to avoid circular dependencies
        from ansible_ai_connect.ai.api.model_pipelines.pipelines import MetaData  # noqa
        from ansible_ai_connect.ai.api.model_pipelines.registry import (  # noqa
            REGISTRY_ENTRY,
        )

        pipelines = [i for i in REGISTRY_ENTRY.keys() if issubclass(i, MetaData)]
        for k in pipelines:
            self.assertTrue(k.__name__ in config)

    @patch.dict(
        os.environ,
        {
            "ANSIBLE_AI_MODEL_MESH_API_TYPE": "wca",
            "ANSIBLE_AI_MODEL_MESH_MODEL_NAME": "a-model",
        },
    )
    def test_use_of_model_mesh_model_name(self):
        with self.assertLogs(logger="root", level="DEBUG") as log:
            settings = self.reload_settings()
            config = json.loads(settings.ANSIBLE_AI_MODEL_MESH_CONFIG)

            self.assertEqual(config["ModelPipelineCompletions"]["config"]["model_id"], "a-model")
            self.assertTrue(
                self.searchInLogOutput("Use of ANSIBLE_AI_MODEL_MESH_MODEL_NAME is deprecated", log)
            )
            self.assertTrue(
                self.searchInLogOutput("Setting the value of ANSIBLE_AI_MODEL_MESH_MODEL_ID", log)
            )

    @patch.dict(
        os.environ,
        {
            "ANSIBLE_AI_MODEL_MESH_API_TYPE": "wca",
            "ANSIBLE_AI_MODEL_MESH_MODEL_NAME": "a-model",
            "ANSIBLE_AI_MODEL_MESH_MODEL_ID": "b-model",
        },
    )
    def test_use_of_model_mesh_model_name_and_model_id(self):
        with self.assertLogs(logger="root", level="DEBUG") as log:
            settings = self.reload_settings()
            config = json.loads(settings.ANSIBLE_AI_MODEL_MESH_CONFIG)

            self.assertEqual(config["ModelPipelineCompletions"]["config"]["model_id"], "b-model")
            self.assertTrue(
                self.searchInLogOutput("Use of ANSIBLE_AI_MODEL_MESH_MODEL_NAME is deprecated", log)
            )
            self.assertTrue(
                self.searchInLogOutput(
                    "ANSIBLE_AI_MODEL_MESH_MODEL_ID is set and will take precedence", log
                )
            )

    @patch.dict(
        os.environ,
        {
            "ANSIBLE_AI_MODEL_MESH_API_TYPE": "wca",
            "ANSIBLE_AI_MODEL_MESH_API_URL": "http://a-url",
            "ANSIBLE_AI_MODEL_MESH_API_KEY": "api-key",
            "ANSIBLE_AI_MODEL_MESH_MODEL_ID": "model-id",
            "ANSIBLE_AI_MODEL_MESH_API_TIMEOUT": "999",
            "ANSIBLE_AI_MODEL_MESH_API_VERIFY_SSL": "True",
            "ANSIBLE_WCA_RETRY_COUNT": "9",
            "ENABLE_HEALTHCHECK_MODEL_MESH": "True",
            "ANSIBLE_WCA_HEALTHCHECK_API_KEY": "health-check-api-key",
            "ANSIBLE_WCA_HEALTHCHECK_MODEL_ID": "health-check-model-id",
            "ANSIBLE_WCA_IDP_URL": "http://idp-url",
            "ANSIBLE_WCA_IDP_LOGIN": "idp-login",
            "ANSIBLE_WCA_IDP_PASSWORD": "idp-password",
            "ANSIBLE_AI_ENABLE_ONE_CLICK_DEFAULT_API_KEY": "trial-api-key",
            "ANSIBLE_AI_ENABLE_ONE_CLICK_DEFAULT_MODEL_ID": "trial-model-id",
        },
    )
    def test_wca_saas(self):
        settings = self.reload_settings()
        config = json.loads(settings.ANSIBLE_AI_MODEL_MESH_CONFIG)

        self.assertEqual(
            config["ModelPipelineCompletions"]["config"]["inference_url"], "http://a-url"
        )
        self.assertEqual(config["ModelPipelineCompletions"]["config"]["api_key"], "api-key")
        self.assertEqual(config["ModelPipelineCompletions"]["config"]["model_id"], "model-id")
        self.assertEqual(config["ModelPipelineCompletions"]["config"]["timeout"], 999)
        self.assertEqual(config["ModelPipelineCompletions"]["config"]["verify_ssl"], True)
        self.assertEqual(config["ModelPipelineCompletions"]["config"]["retry_count"], 9)
        self.assertEqual(config["ModelPipelineCompletions"]["config"]["enable_health_check"], True)
        self.assertEqual(
            config["ModelPipelineCompletions"]["config"]["health_check_api_key"],
            "health-check-api-key",
        )
        self.assertEqual(
            config["ModelPipelineCompletions"]["config"]["health_check_model_id"],
            "health-check-model-id",
        )
        self.assertEqual(config["ModelPipelineCompletions"]["config"]["idp_url"], "http://idp-url")
        self.assertEqual(config["ModelPipelineCompletions"]["config"]["idp_login"], "idp-login")
        self.assertEqual(
            config["ModelPipelineCompletions"]["config"]["idp_password"], "idp-password"
        )
        self.assertEqual(
            config["ModelPipelineCompletions"]["config"]["one_click_default_api_key"],
            "trial-api-key",
        )
        self.assertEqual(
            config["ModelPipelineCompletions"]["config"]["one_click_default_model_id"],
            "trial-model-id",
        )

    @patch.dict(
        os.environ,
        {
            "ANSIBLE_AI_MODEL_MESH_API_TYPE": "wca-onprem",
            "ANSIBLE_AI_MODEL_MESH_API_URL": "http://a-url",
            "ANSIBLE_AI_MODEL_MESH_API_KEY": "api-key",
            "ANSIBLE_AI_MODEL_MESH_MODEL_ID": "model-id",
            "ANSIBLE_AI_MODEL_MESH_API_TIMEOUT": "999",
            "ANSIBLE_AI_MODEL_MESH_API_VERIFY_SSL": "True",
            "ANSIBLE_WCA_RETRY_COUNT": "9",
            "ENABLE_HEALTHCHECK_MODEL_MESH": "True",
            "ANSIBLE_WCA_HEALTHCHECK_API_KEY": "health-check-api-key",
            "ANSIBLE_WCA_HEALTHCHECK_MODEL_ID": "health-check-model-id",
            "ANSIBLE_WCA_USERNAME": "username",
        },
    )
    def test_wca_onprem(self):
        settings = self.reload_settings()
        config = json.loads(settings.ANSIBLE_AI_MODEL_MESH_CONFIG)

        self.assertEqual(
            config["ModelPipelineCompletions"]["config"]["inference_url"], "http://a-url"
        )
        self.assertEqual(config["ModelPipelineCompletions"]["config"]["api_key"], "api-key")
        self.assertEqual(config["ModelPipelineCompletions"]["config"]["model_id"], "model-id")
        self.assertEqual(config["ModelPipelineCompletions"]["config"]["timeout"], 999)
        self.assertEqual(config["ModelPipelineCompletions"]["config"]["verify_ssl"], True)
        self.assertEqual(config["ModelPipelineCompletions"]["config"]["retry_count"], 9)
        self.assertEqual(config["ModelPipelineCompletions"]["config"]["enable_health_check"], True)
        self.assertEqual(
            config["ModelPipelineCompletions"]["config"]["health_check_api_key"],
            "health-check-api-key",
        )
        self.assertEqual(
            config["ModelPipelineCompletions"]["config"]["health_check_model_id"],
            "health-check-model-id",
        )
        self.assertEqual(config["ModelPipelineCompletions"]["config"]["username"], "username")

    @patch.dict(
        os.environ,
        {
            "ANSIBLE_AI_MODEL_MESH_API_TYPE": "wca-dummy",
            "ANSIBLE_AI_MODEL_MESH_API_URL": "http://a-url",
        },
    )
    def test_wca_dummy(self):
        settings = self.reload_settings()
        config = json.loads(settings.ANSIBLE_AI_MODEL_MESH_CONFIG)

        self.assertEqual(
            config["ModelPipelineCompletions"]["config"]["inference_url"], "http://a-url"
        )

    @patch.dict(
        os.environ,
        {
            "ANSIBLE_AI_MODEL_MESH_API_TYPE": "dummy",
            "ANSIBLE_AI_MODEL_MESH_API_URL": "http://a-url",
            "DUMMY_MODEL_RESPONSE_BODY": "dummy-body",
            "DUMMY_MODEL_RESPONSE_MAX_LATENCY_MSEC": "999",
            "DUMMY_MODEL_RESPONSE_LATENCY_USE_JITTER": "True",
        },
    )
    def test_dummy(self):
        settings = self.reload_settings()
        config = json.loads(settings.ANSIBLE_AI_MODEL_MESH_CONFIG)

        self.assertEqual(
            config["ModelPipelineCompletions"]["config"]["inference_url"], "http://a-url"
        )
        self.assertEqual(config["ModelPipelineCompletions"]["config"]["body"], "dummy-body")
        self.assertEqual(config["ModelPipelineCompletions"]["config"]["latency_max_msec"], 999)
        self.assertEqual(config["ModelPipelineCompletions"]["config"]["latency_use_jitter"], True)

    @patch.dict(
        os.environ,
        {
            "ANSIBLE_AI_MODEL_MESH_API_TYPE": "ollama",
            "ANSIBLE_AI_MODEL_MESH_API_URL": "http://a-url",
            "ANSIBLE_AI_MODEL_MESH_MODEL_ID": "model-id",
            "ANSIBLE_AI_MODEL_MESH_API_TIMEOUT": "999",
        },
    )
    def test_ollama(self):
        settings = self.reload_settings()
        config = json.loads(settings.ANSIBLE_AI_MODEL_MESH_CONFIG)

        self.assertEqual(
            config["ModelPipelineCompletions"]["config"]["inference_url"], "http://a-url"
        )
        self.assertEqual(config["ModelPipelineCompletions"]["config"]["model_id"], "model-id")
        self.assertEqual(config["ModelPipelineCompletions"]["config"]["timeout"], 999)

    def test_empty_configuration(self):
        config = load_config_from_str("")

        # Lazy import to avoid circular dependencies
        from ansible_ai_connect.ai.api.model_pipelines.pipelines import MetaData  # noqa
        from ansible_ai_connect.ai.api.model_pipelines.registry import (  # noqa
            REGISTRY_ENTRY,
        )

        pipelines = [i for i in REGISTRY_ENTRY.keys() if issubclass(i, MetaData)]
        for k in pipelines:
            self.assertTrue(k.__name__ in config)
            self.assertEqual(config[k.__name__].provider, "nop")
