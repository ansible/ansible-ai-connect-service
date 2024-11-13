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

from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    ModelPipelineCompletions,
    ModelPipelineContentMatch,
    ModelPipelinePlaybookExplanation,
    ModelPipelinePlaybookGeneration,
    ModelPipelineRoleGeneration,
)
from ansible_ai_connect.ai.api.model_pipelines.tests.test_factory import (
    TestModelPipelineFactoryImplementations,
)
from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base import (
    WCABaseRoleGenerationPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_saas import (
    WCASaaSCompletionsPipeline,
    WCASaaSContentMatchPipeline,
    WCASaaSPlaybookExplanationPipeline,
    WCASaaSPlaybookGenerationPipeline,
)


@override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="wca")
class TestModelPipelineFactory(TestModelPipelineFactoryImplementations):

    def test_completions_pipeline(self):
        self.assert_concrete_implementation(ModelPipelineCompletions, WCASaaSCompletionsPipeline)

    def test_content_match_pipeline(self):
        self.assert_concrete_implementation(ModelPipelineContentMatch, WCASaaSContentMatchPipeline)

    def test_playbook_generation_pipeline(self):
        self.assert_concrete_implementation(
            ModelPipelinePlaybookGeneration, WCASaaSPlaybookGenerationPipeline
        )

    def test_role_generation_pipeline(self):
        self.assert_concrete_implementation(
            ModelPipelineRoleGeneration, WCABaseRoleGenerationPipeline
        )

    def test_playbook_explanation_pipeline(self):
        self.assert_concrete_implementation(
            ModelPipelinePlaybookExplanation, WCASaaSPlaybookExplanationPipeline
        )
