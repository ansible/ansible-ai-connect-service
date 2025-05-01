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

from typing import Type

from ansible_ai_connect.ai.api.model_pipelines.factory import ModelPipelineFactory
from ansible_ai_connect.ai.api.model_pipelines.pipelines import ModelPipeline
from ansible_ai_connect.ai.api.model_pipelines.types import PIPELINE_TYPE
from ansible_ai_connect.healthcheck.backends import HealthCheckSummary
from ansible_ai_connect.main.settings.types import t_model_mesh_api_type
from ansible_ai_connect.test_utils import WisdomServiceAPITestCaseBaseOIDC


class TestModelPipelineHealthCheck(WisdomServiceAPITestCaseBaseOIDC):

    def assert_ok(self, pipeline_type: Type[PIPELINE_TYPE], provider: t_model_mesh_api_type):
        self._assert_status(pipeline_type, provider, "ok")

    def assert_skipped(self, pipeline_type: Type[PIPELINE_TYPE], provider: t_model_mesh_api_type):
        self._assert_status(pipeline_type, provider, "skipped")

    def _assert_status(
        self, pipeline_type: Type[PIPELINE_TYPE], provider: t_model_mesh_api_type, status: str
    ):
        factory = ModelPipelineFactory()

        pipeline: ModelPipeline = factory.get_pipeline(pipeline_type)
        summary: HealthCheckSummary = pipeline.self_test()
        self.assertIsNotNone(summary)
        self.assertTrue("provider" in summary.items)
        self.assertEqual(provider, summary.items["provider"])
        self.assertTrue("models" in summary.items)
        self.assertEqual(status, summary.items["models"])
