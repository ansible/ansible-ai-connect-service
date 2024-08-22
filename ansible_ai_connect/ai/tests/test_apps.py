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
from ansible_ai_connect.test_utils import WisdomServiceLogAwareTestCase
from ansible_ai_connect.users.reports.exceptions import ReportConfigurationException
from ansible_ai_connect.users.reports.postman import (
    GoogleDrivePostman,
    NoopPostman,
    SlackWebApiPostman,
    SlackWebhookPostman,
    StdoutPostman,
)


class TestAiApp(WisdomServiceLogAwareTestCase):
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="grpc")
    def test_grpc_client(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsInstance(app_config.model_mesh_client, GrpcClient)

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="wca")
    def test_wca_client(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsInstance(app_config.model_mesh_client, WCAClient)

    @override_settings(ANSIBLE_WCA_USERNAME="username")
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY="12345")
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="wca-onprem")
    def test_wca_on_prem_client(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsInstance(app_config.model_mesh_client, WCAOnPremClient)

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY="12345")
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="wca-onprem")
    def test_wca_on_prem_client_missing_username(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        with self.assertRaises(WcaUsernameNotFound):
            app_config.ready()

    @override_settings(ANSIBLE_WCA_USERNAME="username")
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="wca-onprem")
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY=None)
    def test_wca_on_prem_client_missing_api_key(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        with self.assertRaises(WcaKeyNotFound):
            app_config.ready()

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="http")
    def test_http_client(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsInstance(app_config.model_mesh_client, HttpClient)

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="wca-dummy")
    def test_wca_dummy_client(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsInstance(app_config.model_mesh_client, DummyWCAClient)

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="dummy")
    def test_mock_client(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsInstance(app_config.model_mesh_client, DummyClient)

    @override_settings(ENABLE_ARI_POSTPROCESS=True)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="dummy")
    def test_enable_ari_default(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsNotNone(app_config.get_ari_caller())

    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="dummy")
    def test_disable_ari_default(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsNone(app_config.get_ari_caller())

    @override_settings(ENABLE_ARI_POSTPROCESS=True)
    @override_settings(WCA_ENABLE_ARI_POSTPROCESS=True)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="wca")
    def test_enable_ari_wca_cloud(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsNotNone(app_config.get_ari_caller())

    @override_settings(ENABLE_ARI_POSTPROCESS=True)
    @override_settings(WCA_ENABLE_ARI_POSTPROCESS=False)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="wca")
    def test_enable_ari_wca_cloud_disable_wca(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsNone(app_config.get_ari_caller())

    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @override_settings(WCA_ENABLE_ARI_POSTPROCESS=True)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="wca")
    def test_disable_ari_wca_cloud_enable_wca(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsNone(app_config.get_ari_caller())

    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @override_settings(WCA_ENABLE_ARI_POSTPROCESS=False)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="wca")
    def test_disable_ari_wca_cloud_disable_wca(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsNone(app_config.get_ari_caller())

    @override_settings(ENABLE_ARI_POSTPROCESS=True)
    @override_settings(WCA_ENABLE_ARI_POSTPROCESS=True)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="wca-onprem")
    @override_settings(ANSIBLE_WCA_USERNAME="username")
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY="api-key")
    def test_enable_ari_wca_onprem(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsNotNone(app_config.get_ari_caller())

    @override_settings(ENABLE_ARI_POSTPROCESS=True)
    @override_settings(WCA_ENABLE_ARI_POSTPROCESS=False)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="wca-onprem")
    @override_settings(ANSIBLE_WCA_USERNAME="username")
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY="api-key")
    def test_enable_ari_wca_onprem_disable_wca(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsNone(app_config.get_ari_caller())

    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @override_settings(WCA_ENABLE_ARI_POSTPROCESS=True)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="wca-onprem")
    @override_settings(ANSIBLE_WCA_USERNAME="username")
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY="api-key")
    def test_disable_ari_wca_onprem_enable_wca(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsNone(app_config.get_ari_caller())

    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @override_settings(WCA_ENABLE_ARI_POSTPROCESS=False)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="wca-onprem")
    @override_settings(ANSIBLE_WCA_USERNAME="username")
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY="api-key")
    def test_disable_ari_wca_onprem_disable_wca(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsNone(app_config.get_ari_caller())

    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=True)
    def test_enable_ansible_lint(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsNotNone(app_config.get_ansible_lint_caller())

    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=False)
    def test_disable_ansible_lint(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsNone(app_config.get_ansible_lint_caller())

    @override_settings(ANSIBLE_AI_ONE_CLICK_REPORTS_POSTMAN="none")
    def test_reports_postman_none(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsInstance(app_config.get_reports_postman(), NoopPostman)

    @override_settings(ANSIBLE_AI_ONE_CLICK_REPORTS_POSTMAN="stdout")
    def test_reports_postman_stdout(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsInstance(app_config.get_reports_postman(), StdoutPostman)

    @override_settings(ANSIBLE_AI_ONE_CLICK_REPORTS_POSTMAN="slack-webhook")
    @override_settings(ANSIBLE_AI_ONE_CLICK_REPORTS_CONFIG={"slack-webhook-url": "webhook-url"})
    def test_reports_postman_slack_webhook(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsInstance(app_config.get_reports_postman(), SlackWebhookPostman)

    @override_settings(ANSIBLE_AI_ONE_CLICK_REPORTS_POSTMAN="slack-webhook")
    @override_settings(ANSIBLE_AI_ONE_CLICK_REPORTS_CONFIG={})
    def test_reports_postman_slack_webhook_missing_webhook_url(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        with self.assertRaises(ReportConfigurationException):
            app_config.get_reports_postman()

    @override_settings(ANSIBLE_AI_ONE_CLICK_REPORTS_POSTMAN="slack-webapi")
    @override_settings(
        ANSIBLE_AI_ONE_CLICK_REPORTS_CONFIG={
            "slack-token": "webapi-token",
            "slack-channel-id": "webapi-channel",
        }
    )
    def test_reports_postman_slack_webapi(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsInstance(app_config.get_reports_postman(), SlackWebApiPostman)

    @override_settings(ANSIBLE_AI_ONE_CLICK_REPORTS_POSTMAN="slack-webapi")
    @override_settings(ANSIBLE_AI_ONE_CLICK_REPORTS_CONFIG={"slack-channel-id": "webapi-channel"})
    def test_reports_postman_slack_webapi_missing_token(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        with self.assertRaises(ReportConfigurationException):
            app_config.get_reports_postman()

    @override_settings(ANSIBLE_AI_ONE_CLICK_REPORTS_POSTMAN="slack-webapi")
    @override_settings(ANSIBLE_AI_ONE_CLICK_REPORTS_CONFIG={"slack-token": "webapi-token"})
    def test_reports_postman_slack_webapi_missing_channel_id(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        with self.assertRaises(ReportConfigurationException):
            app_config.get_reports_postman()

    @override_settings(ANSIBLE_AI_ONE_CLICK_REPORTS_POSTMAN="google-drive")
    @override_settings(
        ANSIBLE_AI_ONE_CLICK_REPORTS_CONFIG={
            "gdrive-folder-name": "test-folder",
            "gdrive-project-id": "test-project-id",
            "gdrive-private-key-id": "test-private-key-id",
            "gdrive-private-key": "test-private-key",
            "gdrive-client-email": "test-client-email",
            "gdrive-client-id": "test-client-id",
        }
    )
    def test_reports_postman_google_drive(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsInstance(app_config.get_reports_postman(), GoogleDrivePostman)

    @override_settings(ANSIBLE_AI_ONE_CLICK_REPORTS_POSTMAN="google-drive")
    @override_settings(ANSIBLE_AI_ONE_CLICK_REPORTS_CONFIG={})
    def test_reports_postman_google_drive_missing_folder_name(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        with self.assertRaises(ReportConfigurationException):
            app_config.get_reports_postman()

    @override_settings(ANSIBLE_AI_ONE_CLICK_REPORTS_POSTMAN="google-drive")
    @override_settings(
        ANSIBLE_AI_ONE_CLICK_REPORTS_CONFIG={
            "gdrive-folder-name": "test-folder",
        }
    )
    def test_reports_postman_google_drive_missing_project_id(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        with self.assertRaises(ReportConfigurationException):
            app_config.get_reports_postman()

    @override_settings(ANSIBLE_AI_ONE_CLICK_REPORTS_POSTMAN="google-drive")
    @override_settings(
        ANSIBLE_AI_ONE_CLICK_REPORTS_CONFIG={
            "gdrive-folder-name": "test-folder",
            "gdrive-project-id": "test-project-id",
        }
    )
    def test_reports_postman_google_drive_missing_private_key_id(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        with self.assertRaises(ReportConfigurationException):
            app_config.get_reports_postman()

    @override_settings(ANSIBLE_AI_ONE_CLICK_REPORTS_POSTMAN="google-drive")
    @override_settings(
        ANSIBLE_AI_ONE_CLICK_REPORTS_CONFIG={
            "gdrive-folder-name": "test-folder",
            "gdrive-project-id": "test-project-id",
            "gdrive-private-key-id": "test-private-key-id",
        }
    )
    def test_reports_postman_google_drive_missing_private_key(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        with self.assertRaises(ReportConfigurationException):
            app_config.get_reports_postman()

    @override_settings(ANSIBLE_AI_ONE_CLICK_REPORTS_POSTMAN="google-drive")
    @override_settings(
        ANSIBLE_AI_ONE_CLICK_REPORTS_CONFIG={
            "gdrive-folder-name": "test-folder",
            "gdrive-project-id": "test-project-id",
            "gdrive-private-key-id": "test-private-key-id",
            "gdrive-private-key": "test-private-key",
        }
    )
    def test_reports_postman_google_drive_missing_client_email(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        with self.assertRaises(ReportConfigurationException):
            app_config.get_reports_postman()

    @override_settings(ANSIBLE_AI_ONE_CLICK_REPORTS_POSTMAN="google-drive")
    @override_settings(
        ANSIBLE_AI_ONE_CLICK_REPORTS_CONFIG={
            "gdrive-folder-name": "test-folder",
            "gdrive-project-id": "test-project-id",
            "gdrive-private-key-id": "test-private-key-id",
            "gdrive-private-key": "test-private-key",
            "gdrive-client-email": "test-client-email",
        }
    )
    def test_reports_postman_google_drive_missing_client_id(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        with self.assertRaises(ReportConfigurationException):
            app_config.get_reports_postman()

    @override_settings(ANSIBLE_AI_ONE_CLICK_REPORTS_POSTMAN="banana")
    def test_reports_postman_rogue_setting(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        with self.assertLogs(logger="root", level="DEBUG") as log:
            with self.assertRaises(KeyError):
                app_config.get_reports_postman()
            self.assertInLog("Unexpected ANSIBLE_AI_ONE_CLICK_REPORTS_POSTMAN value: banana", log)
