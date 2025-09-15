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

from unittest import mock

from django.test import override_settings

from ansible_ai_connect.main import ssl_manager

from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    ModelPipelineChatBot,
    ModelPipelineCompletions,
    ModelPipelineContentMatch,
    ModelPipelinePlaybookExplanation,
    ModelPipelinePlaybookGeneration,
    ModelPipelineRoleExplanation,
    ModelPipelineRoleGeneration,
    ModelPipelineStreamingChatBot,
)
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_config
from ansible_ai_connect.ai.api.model_pipelines.tests.test_healthcheck import (
    TestModelPipelineHealthCheck,
)
from ansible_ai_connect.ai.api.model_pipelines.tests.test_wca_client import MockResponse


@override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("http"))
class TestModelPipelineFactory(TestModelPipelineHealthCheck):

    @mock.patch("requests.Session.get", return_value=MockResponse(None, 200))
    def test_completions_healthcheck(self, *args, **kwargs):
        self.assert_ok(ModelPipelineCompletions, "http")

    def test_content_match_healthcheck(self):
        self.assert_skipped(ModelPipelineContentMatch, "nop")

    def test_playbook_generation_healthcheck(self):
        self.assert_skipped(ModelPipelinePlaybookGeneration, "nop")

    def test_role_generation_healthcheck(self):
        self.assert_skipped(ModelPipelineRoleGeneration, "nop")

    def test_playbook_explanation_healthcheck(self):
        self.assert_skipped(ModelPipelinePlaybookExplanation, "nop")

    def test_role_explanation_healthcheck(self):
        self.assert_skipped(ModelPipelineRoleExplanation, "nop")

    @mock.patch.object(ssl_manager.ssl_manager, "get_requests_session")
    def test_chatbot_healthcheck(self, mock_session_factory):
        mock_session = mock.Mock()
        mock_session.get.return_value = MockResponse({"ready": True}, 200)
        mock_session_factory.return_value = mock_session
        self.assert_ok(ModelPipelineChatBot, "http")

    @mock.patch.object(ssl_manager.ssl_manager, "get_requests_session")
    def test_streaming_chatbot_healthcheck(self, mock_session_factory):
        mock_session = mock.Mock()
        mock_session.get.return_value = MockResponse({"ready": True}, 200)
        mock_session_factory.return_value = mock_session
        self.assert_ok(ModelPipelineStreamingChatBot, "http")
