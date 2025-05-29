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
from rest_framework.test import APITransactionTestCase

from ansible_ai_connect.ai.api.model_pipelines.tests import mock_config
from ansible_ai_connect.ai.api.versions.v1.test_base import API_VERSION
from ansible_ai_connect.test_utils import WisdomServiceAPITestCaseBaseOIDC
from ansible_ai_connect.users.tests.test_users import (
    TestTelemetryOptInOut,
    TestThirdPartyAuthentication,
    TestUsers,
)


class TestUsersVersion1(TestUsers):
    api_version = API_VERSION


class TestThirdPartyAuthenticationVersion1(TestThirdPartyAuthentication):
    api_version = API_VERSION


class TestTelemetryOptInOutVersion1(TestTelemetryOptInOut):
    api_version = API_VERSION


@override_settings(ANSIBLE_AI_ENABLE_USER_TOKEN_GEN=False)
@override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("wca-dummy"))
@override_settings(AUTHZ_BACKEND_TYPE="dummy")
@override_settings(AUTHZ_DUMMY_ORGS_WITH_SUBSCRIPTION="*")
@override_settings(WCA_SECRET_DUMMY_SECRETS="1981:valid<sep>a_model_id")
@override_settings(DEBUG_FORCE_PIPELINE_RELOAD=True)
class TestTokenGenVersion1(WisdomServiceAPITestCaseBaseOIDC, APITransactionTestCase):
    api_version = API_VERSION

    def test_ANSIBLE_AI_ENABLE_USER_TOKEN_GEN_settings_key(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(self.api_version_reverse("user_token"))
        self.assertEqual(r.status_code, 403)

    @override_settings(ANSIBLE_AI_ENABLE_USER_TOKEN_GEN=True)
    def test_gen_token(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(self.api_version_reverse("user_token"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.data,
            {
                "bearer_token": {
                    "access_token": "a_dummy_token_for_your_test",
                    "expiration": 123154,
                    "expires_in": 600,
                },
                "inference_url": "http://localhost",
            },
        )
