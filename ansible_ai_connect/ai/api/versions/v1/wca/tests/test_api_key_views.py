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

from http import HTTPStatus

from django.test import override_settings

from ansible_ai_connect.ai.api.versions.v1.test_base import API_VERSION
from ansible_ai_connect.ai.api.wca.tests.test_api_key_views import (
    TestWCAApiKeyValidatorView,
    TestWCAApiKeyView,
    TestWCAApiKeyViewAsNonSubscriber,
)


class TestWCAApiKeyViewVersion1(TestWCAApiKeyView):
    api_version = API_VERSION

    @override_settings(DEBUG=False, DEPLOYMENT_MODE="DUMMY_VALUE")
    def test_get_key_non_saas_non_debug(self):
        r = self.client.get(self.api_version_reverse("wca_api_key"))
        self.assertEqual(r.status_code, HTTPStatus.NOT_IMPLEMENTED)

    @override_settings(DEBUG=False, DEPLOYMENT_MODE="DUMMY_VALUE")
    def test_post_key_non_saas_non_debug(self):
        r = self.client.post(self.api_version_reverse("wca_api_key"))
        self.assertEqual(r.status_code, HTTPStatus.NOT_IMPLEMENTED)

    @override_settings(DEBUG=False, DEPLOYMENT_MODE="DUMMY_VALUE")
    def test_delete_key_non_saas_non_debug(self):
        r = self.client.delete(self.api_version_reverse("wca_api_key"))
        self.assertEqual(r.status_code, HTTPStatus.NOT_IMPLEMENTED)


class TestWCAApiKeyViewAsNonSubscriberVersion1(TestWCAApiKeyViewAsNonSubscriber):
    api_version = API_VERSION


class TestWCAApiKeyValidatorViewVersion1(TestWCAApiKeyValidatorView):
    api_version = API_VERSION

    @override_settings(DEBUG=False, DEPLOYMENT_MODE="DUMMY_VALUE")
    def test_validate_non_saas_non_debug(self):
        r = self.client.get(self.api_version_reverse("wca_api_key_validator"))
        self.assertEqual(r.status_code, HTTPStatus.NOT_IMPLEMENTED)
