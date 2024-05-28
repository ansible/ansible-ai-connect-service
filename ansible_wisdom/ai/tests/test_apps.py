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

from django.apps.config import AppConfig
from django.test import override_settings
from rest_framework.test import APITestCase

from ansible_ai_connect.ai.api.model_client.dummy_client import DummyClient
from ansible_ai_connect.ai.api.model_client.exceptions import (
    WcaKeyNotFound,
    WcaUsernameNotFound,
)
from ansible_ai_connect.ai.api.model_client.grpc_client import GrpcClient
from ansible_ai_connect.ai.api.model_client.http_client import HttpClient
from ansible_ai_connect.ai.api.model_client.wca_client import (
    DummyWCAClient,
    WCAClient,
    WCAOnPremClient,
)


class TestAiApp(APITestCase):
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE='grpc')
    def test_grpc_client(self):
        app_config = AppConfig.create('ansible_ai_connect.ai')
        app_config.ready()
        self.assertIsInstance(app_config.model_mesh_client, GrpcClient)

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE='wca')
    def test_wca_client(self):
        app_config = AppConfig.create('ansible_ai_connect.ai')
        app_config.ready()
        self.assertIsInstance(app_config.model_mesh_client, WCAClient)

    @override_settings(ANSIBLE_WCA_USERNAME='username')
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY='12345')
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE='wca-onprem')
    def test_wca_on_prem_client(self):
        app_config = AppConfig.create('ansible_ai_connect.ai')
        app_config.ready()
        self.assertIsInstance(app_config.model_mesh_client, WCAOnPremClient)

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY='12345')
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE='wca-onprem')
    def test_wca_on_prem_client_missing_username(self):
        app_config = AppConfig.create('ansible_ai_connect.ai')
        with self.assertRaises(WcaUsernameNotFound):
            app_config.ready()

    @override_settings(ANSIBLE_WCA_USERNAME='username')
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE='wca-onprem')
    def test_wca_on_prem_client_missing_api_key(self):
        app_config = AppConfig.create('ansible_ai_connect.ai')
        with self.assertRaises(WcaKeyNotFound):
            app_config.ready()

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE='http')
    def test_http_client(self):
        app_config = AppConfig.create('ansible_ai_connect.ai')
        app_config.ready()
        self.assertIsInstance(app_config.model_mesh_client, HttpClient)

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE='wca-dummy')
    def test_wca_dummy_client(self):
        app_config = AppConfig.create('ansible_ai_connect.ai')
        app_config.ready()
        self.assertIsInstance(app_config.model_mesh_client, DummyWCAClient)

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE='dummy')
    def test_mock_client(self):
        app_config = AppConfig.create('ansible_ai_connect.ai')
        app_config.ready()
        self.assertIsInstance(app_config.model_mesh_client, DummyClient)

    @override_settings(ENABLE_ARI_POSTPROCESS=True)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE='dummy')
    def test_enable_ari_default(self):
        app_config = AppConfig.create('ansible_ai_connect.ai')
        app_config.ready()
        self.assertIsNotNone(app_config.get_ari_caller())

    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE='dummy')
    def test_disable_ari_default(self):
        app_config = AppConfig.create('ansible_ai_connect.ai')
        app_config.ready()
        self.assertIsNone(app_config.get_ari_caller())

    @override_settings(ENABLE_ARI_POSTPROCESS=True)
    @override_settings(ENABLE_ARI_POSTPROCESS_FOR_WCA=True)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE='wca')
    def test_enable_ari_wca_cloud(self):
        app_config = AppConfig.create('ansible_ai_connect.ai')
        app_config.ready()
        self.assertIsNotNone(app_config.get_ari_caller())

    @override_settings(ENABLE_ARI_POSTPROCESS=True)
    @override_settings(ENABLE_ARI_POSTPROCESS_FOR_WCA=False)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE='wca')
    def test_enable_ari_wca_cloud_disable_wca(self):
        app_config = AppConfig.create('ansible_ai_connect.ai')
        app_config.ready()
        self.assertIsNone(app_config.get_ari_caller())

    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @override_settings(ENABLE_ARI_POSTPROCESS_FOR_WCA=True)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE='wca')
    def test_disable_ari_wca_cloud_enable_wca(self):
        app_config = AppConfig.create('ansible_ai_connect.ai')
        app_config.ready()
        self.assertIsNone(app_config.get_ari_caller())

    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @override_settings(ENABLE_ARI_POSTPROCESS_FOR_WCA=False)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE='wca')
    def test_disable_ari_wca_cloud_disable_wca(self):
        app_config = AppConfig.create('ansible_ai_connect.ai')
        app_config.ready()
        self.assertIsNone(app_config.get_ari_caller())

    @override_settings(ENABLE_ARI_POSTPROCESS=True)
    @override_settings(ENABLE_ARI_POSTPROCESS_FOR_WCA=True)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE='wca-onprem')
    @override_settings(ANSIBLE_WCA_USERNAME="username")
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY="api-key")
    def test_enable_ari_wca_onprem(self):
        app_config = AppConfig.create('ansible_ai_connect.ai')
        app_config.ready()
        self.assertIsNotNone(app_config.get_ari_caller())

    @override_settings(ENABLE_ARI_POSTPROCESS=True)
    @override_settings(ENABLE_ARI_POSTPROCESS_FOR_WCA=False)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE='wca-onprem')
    @override_settings(ANSIBLE_WCA_USERNAME="username")
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY="api-key")
    def test_enable_ari_wca_onprem_disable_wca(self):
        app_config = AppConfig.create('ansible_ai_connect.ai')
        app_config.ready()
        self.assertIsNone(app_config.get_ari_caller())

    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @override_settings(ENABLE_ARI_POSTPROCESS_FOR_WCA=True)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE='wca-onprem')
    @override_settings(ANSIBLE_WCA_USERNAME="username")
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY="api-key")
    def test_disable_ari_wca_onprem_enable_wca(self):
        app_config = AppConfig.create('ansible_ai_connect.ai')
        app_config.ready()
        self.assertIsNone(app_config.get_ari_caller())

    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @override_settings(ENABLE_ARI_POSTPROCESS_FOR_WCA=False)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE='wca-onprem')
    @override_settings(ANSIBLE_WCA_USERNAME="username")
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY="api-key")
    def test_disable_ari_wca_onprem_disable_wca(self):
        app_config = AppConfig.create('ansible_ai_connect.ai')
        app_config.ready()
        self.assertIsNone(app_config.get_ari_caller())

    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=True)
    def test_enable_ansible_lint(self):
        app_config = AppConfig.create('ansible_ai_connect.ai')
        app_config.ready()
        self.assertIsNotNone(app_config.get_ansible_lint_caller())

    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=False)
    def test_disable_ansible_lint(self):
        app_config = AppConfig.create('ansible_ai_connect.ai')
        app_config.ready()
        self.assertIsNone(app_config.get_ansible_lint_caller())
