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

from ansible_ai_connect.ai.api.tests.test_role_explanation_view import (
    TestRoleExplanationViewDummy as TestRoleExplanationView,
)
from ansible_ai_connect.ai.api.versions.v1.test_base import API_VERSION


class TestRoleExplanationViewVersion1(TestRoleExplanationView):
    api_version = API_VERSION

    def test_explanation_role_version_url(self):
        url = self.api_version_reverse("explanations/role")
        self.assertEqual(url, f"/api/{self.api_version}/ai/explanations/role/")
