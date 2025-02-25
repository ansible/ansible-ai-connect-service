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
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_pipeline_config
from ansible_ai_connect.ai.api.model_pipelines.wca.configuration_saas import (
    WCASaaSConfiguration,
    WCASaaSConfigurationSerializer,
)
from ansible_ai_connect.test_utils import WisdomServiceAPITestCaseBaseOIDC


class TestWCASaaSConfigurationSerializer(WisdomServiceAPITestCaseBaseOIDC):

    def test_serializer_with_api_key(self):
        config: WCASaaSConfiguration = mock_pipeline_config("wca")
        serializer = WCASaaSConfigurationSerializer(data=config.__dict__)
        self.assertTrue(serializer.is_valid())

    def test_serializer_without_api_key(self):
        config: WCASaaSConfiguration = mock_pipeline_config("wca", api_key=None)
        serializer = WCASaaSConfigurationSerializer(data=config.__dict__)
        self.assertTrue(serializer.is_valid())

    def test_serializer_with_idp_url(self):
        config: WCASaaSConfiguration = mock_pipeline_config("wca")
        serializer = WCASaaSConfigurationSerializer(data=config.__dict__)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["idp_url"], "an-idp-url")

    def test_serializer_without_idp_url(self):
        config: WCASaaSConfiguration = mock_pipeline_config("wca")
        del config.__dict__["idp_url"]
        serializer = WCASaaSConfigurationSerializer(data=config.__dict__)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["idp_url"], "https://iam.cloud.ibm.com/identity")
