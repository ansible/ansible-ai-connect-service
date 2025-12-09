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

from ansible_ai_connect.ai.api.model_pipelines.dummy.pipelines import (
    DummyCompletionsPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.http.pipelines import (
    HttpCompletionsPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import ModelPipelineCompletions
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_config
from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_dummy import (
    WCADummyCompletionsPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_onprem import (
    WCAOnPremCompletionsPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_saas import (
    WCASaaSCompletionsPipeline,
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
    @override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("wca"))
    def test_wca_client(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsInstance(
            app_config.get_model_pipeline(ModelPipelineCompletions), WCASaaSCompletionsPipeline
        )

    @override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("wca-onprem"))
    def test_wca_on_prem_client(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsInstance(
            app_config.get_model_pipeline(ModelPipelineCompletions), WCAOnPremCompletionsPipeline
        )

    @override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("http"))
    def test_http_client(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsInstance(
            app_config.get_model_pipeline(ModelPipelineCompletions), HttpCompletionsPipeline
        )

    @override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("wca-dummy"))
    def test_wca_dummy_client(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsInstance(
            app_config.get_model_pipeline(ModelPipelineCompletions), WCADummyCompletionsPipeline
        )

    @override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("dummy"))
    def test_mock_client(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
        self.assertIsInstance(
            app_config.get_model_pipeline(ModelPipelineCompletions), DummyCompletionsPipeline
        )

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

    @override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("dummy"))
    def test_default(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()

    @override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("wca"))
    def test_wca_cloud_enable_wca(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()

    @override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("wca"))
    def test_wca_cloud_disable_wca(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()

    @override_settings(
        ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("wca-onprem", enable_ari_postprocessing=True)
    )
    def test_wca_onprem_enable_wca(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()

    @override_settings(
        ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("wca-onprem", enable_ari_postprocessing=False)
    )
    def test_wca_onprem_disable_wca(self):
        app_config = AppConfig.create("ansible_ai_connect.ai")
        app_config.ready()
