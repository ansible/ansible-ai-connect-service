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

from django.test import override_settings

from ansible_ai_connect.ai.api.model_pipelines.nop.pipelines import (
    NopChatBotPipeline,
    NopContentMatchPipeline,
    NopStreamingChatBotPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.ollama.pipelines import (
    OllamaCompletionsPipeline,
    OllamaPlaybookExplanationPipeline,
    OllamaPlaybookGenerationPipeline,
    OllamaRoleExplanationPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    ModelPipelineChatBot,
    ModelPipelineCompletions,
    ModelPipelineContentMatch,
    ModelPipelinePlaybookExplanation,
    ModelPipelinePlaybookGeneration,
    ModelPipelineRoleExplanation,
    ModelPipelineStreamingChatBot,
)
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_config
from ansible_ai_connect.ai.api.model_pipelines.tests.test_factory import (
    TestModelPipelineFactoryImplementations,
)


@override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("ollama"))
class TestModelPipelineFactory(TestModelPipelineFactoryImplementations):

    def test_completions_pipeline(self):
        self.assert_concrete_implementation(ModelPipelineCompletions, OllamaCompletionsPipeline)

    def test_content_match_pipeline(self):
        self.assert_default_implementation(ModelPipelineContentMatch, NopContentMatchPipeline)

    def test_playbook_generation_pipeline(self):
        self.assert_concrete_implementation(
            ModelPipelinePlaybookGeneration, OllamaPlaybookGenerationPipeline
        )

    def test_playbook_explanation_pipeline(self):
        self.assert_concrete_implementation(
            ModelPipelinePlaybookExplanation, OllamaPlaybookExplanationPipeline
        )

    def test_role_explanation_pipeline(self):
        self.assert_concrete_implementation(
            ModelPipelineRoleExplanation, OllamaRoleExplanationPipeline
        )

    def test_chatbot_pipeline(self):
        self.assert_default_implementation(ModelPipelineChatBot, NopChatBotPipeline)

    def test_streaming_chatbot_pipeline(self):
        self.assert_default_implementation(
            ModelPipelineStreamingChatBot, NopStreamingChatBotPipeline
        )
