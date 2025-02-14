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

from ansible_ai_connect.ai.api.tests.test_views import (
    TestContentMatchesWCAView,
    TestContentMatchesWCAViewErrors,
    TestContentMatchesWCAViewSegmentEvents,
    TestExplanationFeatureEnableForWcaOnprem,
    TestExplanationViewWithWCA,
    TestGenerationFeatureEnableForWcaOnprem,
    TestGenerationView,
    TestGenerationViewWithWCA,
)
from ansible_ai_connect.ai.api.versions.v1.test_base import API_VERSION


class TestContentMatchesWCAViewVersion1(TestContentMatchesWCAView):
    api_version = API_VERSION


class TestContentMatchesWCAViewErrorsVersion1(TestContentMatchesWCAViewErrors):
    api_version = API_VERSION


class TestContentMatchesWCAViewSegmentEventsVersion1(TestContentMatchesWCAViewSegmentEvents):
    api_version = API_VERSION


class TestExplanationFeatureEnableForWcaOnpremVersion1(TestExplanationFeatureEnableForWcaOnprem):
    api_version = API_VERSION


class TestExplanationViewWithWCAVersion1(TestExplanationViewWithWCA):
    api_version = API_VERSION


class TestGenerationFeatureEnableForWcaOnpremVersion1(TestGenerationFeatureEnableForWcaOnprem):
    api_version = API_VERSION


class TestGenerationViewVersion1(TestGenerationView):
    api_version = API_VERSION

    def test_generation_playbook_version_url(self):
        url = self.api_version_reverse("generations/playbook")
        self.assertEqual(url, f"/api/{self.api_version}/ai/generations/playbook/")


class TestGenerationViewWithWCAVersion1(TestGenerationViewWithWCA):
    api_version = API_VERSION
