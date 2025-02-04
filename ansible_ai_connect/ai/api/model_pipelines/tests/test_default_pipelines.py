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

from ansible_ai_connect.ai.api.model_pipelines.factory import ModelPipelineFactory
from ansible_ai_connect.ai.api.model_pipelines.nop.pipelines import NopChatBotPipeline
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    MetaData,
    ModelPipelineChatBot,
)
from ansible_ai_connect.ai.api.model_pipelines.registry import REGISTRY, REGISTRY_ENTRY
from ansible_ai_connect.test_utils import WisdomServiceAPITestCaseBaseOIDC


class TestDefaultModelPipelines(WisdomServiceAPITestCaseBaseOIDC):

    @override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG="{}")
    def test_default_pipeline_when_not_defined(self):
        factory = ModelPipelineFactory()

        # The configuration is empty. All pipelines should fall back to the NOP variety
        pipelines = list(filter(lambda p: issubclass(p, MetaData), REGISTRY_ENTRY.keys()))
        for pipeline in pipelines:
            nop = REGISTRY["nop"][pipeline]
            with self.assertLogs(logger="root", level="INFO") as log:
                implementation = factory.get_pipeline(pipeline)
                self.assertIsNotNone(implementation)
                self.assertIsInstance(implementation, nop)
                self.assertInLog(
                    f"Using NOP implementation for '{pipeline.__name__}'.",
                    log,
                )

    @override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG="ModelPipelineChatBot:\n  provider: dummy")
    def test_default_pipeline_when_not_implemented(self):
        factory = ModelPipelineFactory()

        # ChatBot is configured to use "dummy" however there is no "dummy" ChatBot implementation
        with self.assertLogs(logger="root", level="INFO") as log:
            pipeline = factory.get_pipeline(ModelPipelineChatBot)
            self.assertIsNotNone(pipeline)
            self.assertIsInstance(pipeline, NopChatBotPipeline)
            self.assertInLog(
                "Using NOP implementation for 'ModelPipelineChatBot'.",
                log,
            )
