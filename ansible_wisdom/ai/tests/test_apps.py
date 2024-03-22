from django.apps.config import AppConfig
from django.test import override_settings
from rest_framework.test import APITestCase

from ansible_wisdom.ai.api.model_client.dummy_client import DummyClient
from ansible_wisdom.ai.api.model_client.exceptions import (
    WcaKeyNotFound,
    WcaUsernameNotFound,
)
from ansible_wisdom.ai.api.model_client.grpc_client import GrpcClient
from ansible_wisdom.ai.api.model_client.http_client import HttpClient
from ansible_wisdom.ai.api.model_client.wca_client import (
    DummyWCAClient,
    WCAClient,
    WCAOnPremClient,
)


class TestAiApp(APITestCase):
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE='grpc')
    def test_grpc_client(self):
        app_config = AppConfig.create('ansible_wisdom.ai')
        app_config.ready()
        self.assertIsInstance(app_config.model_mesh_client, GrpcClient)

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE='wca')
    def test_wca_client(self):
        app_config = AppConfig.create('ansible_wisdom.ai')
        app_config.ready()
        self.assertIsInstance(app_config.model_mesh_client, WCAClient)

    @override_settings(ANSIBLE_WCA_USERNAME='username')
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY='12345')
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE='wca-onprem')
    def test_wca_on_prem_client(self):
        app_config = AppConfig.create('ansible_wisdom.ai')
        app_config.ready()
        self.assertIsInstance(app_config.model_mesh_client, WCAOnPremClient)

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY='12345')
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE='wca-onprem')
    def test_wca_on_prem_client_missing_username(self):
        app_config = AppConfig.create('ansible_wisdom.ai')
        with self.assertRaises(WcaUsernameNotFound):
            app_config.ready()

    @override_settings(ANSIBLE_WCA_USERNAME='username')
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE='wca-onprem')
    def test_wca_on_prem_client_missing_api_key(self):
        app_config = AppConfig.create('ansible_wisdom.ai')
        with self.assertRaises(WcaKeyNotFound):
            app_config.ready()

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE='http')
    def test_http_client(self):
        app_config = AppConfig.create('ansible_wisdom.ai')
        app_config.ready()
        self.assertIsInstance(app_config.model_mesh_client, HttpClient)

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE='wca-dummy')
    def test_wca_dummy_client(self):
        app_config = AppConfig.create('ansible_wisdom.ai')
        app_config.ready()
        self.assertIsInstance(app_config.model_mesh_client, DummyWCAClient)

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE='dummy')
    def test_mock_client(self):
        app_config = AppConfig.create('ansible_wisdom.ai')
        app_config.ready()
        self.assertIsInstance(app_config.model_mesh_client, DummyClient)

    @override_settings(ENABLE_ARI_POSTPROCESS=True)
    def test_enable_ari(self):
        app_config = AppConfig.create('ansible_wisdom.ai')
        app_config.ready()
        self.assertIsNotNone(app_config.get_ari_caller())

    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_disable_ari(self):
        app_config = AppConfig.create('ansible_wisdom.ai')
        app_config.ready()
        self.assertIsNone(app_config.get_ari_caller())

    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=True)
    def test_enable_ansible_lint(self):
        app_config = AppConfig.create('ansible_wisdom.ai')
        app_config.ready()
        self.assertIsNotNone(app_config.get_ansible_lint_caller())

    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=False)
    def test_disable_ansible_lint(self):
        app_config = AppConfig.create('ansible_wisdom.ai')
        app_config.ready()
        self.assertIsNone(app_config.get_ansible_lint_caller())
