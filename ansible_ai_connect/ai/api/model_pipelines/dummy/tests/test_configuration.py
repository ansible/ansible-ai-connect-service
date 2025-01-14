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

from ansible_ai_connect.ai.api.model_pipelines.dummy.configuration import (
    DEFAULT_BODY,
    DummyConfiguration,
    DummyConfigurationSerializer,
)
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_pipeline_config
from ansible_ai_connect.test_utils import WisdomServiceAPITestCaseBaseOIDC


class TestDummyConfigurationSerializer(WisdomServiceAPITestCaseBaseOIDC):

    def test_empty(self):
        serializer = DummyConfigurationSerializer(data={})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["enable_health_check"], False)
        self.assertEqual(serializer.validated_data["latency_use_jitter"], False)
        self.assertEqual(serializer.validated_data["latency_max_msec"], 3000)
        self.assertEqual(serializer.validated_data["body"], DEFAULT_BODY)

    def test_serializer_with_body(self):
        config: DummyConfiguration = mock_pipeline_config("dummy")
        serializer = DummyConfigurationSerializer(data=config.__dict__)
        self.assertTrue(serializer.is_valid())

    def test_serializer_without_body(self):
        config: DummyConfiguration = mock_pipeline_config("dummy")
        del config.__dict__["body"]
        serializer = DummyConfigurationSerializer(data=config.__dict__)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["body"], DEFAULT_BODY)
