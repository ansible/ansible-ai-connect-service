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

from ansible_ai_connect.ai.api.telemetry.tests.test_api_telemetry_settings_views import (
    TestTelemetrySettingsView,
    TestTelemetrySettingsViewAsNonSubscriber,
)
from ansible_ai_connect.ai.api.versions.v1.test_base import API_VERSION


class TestTelemetrySettingsViewVersion1(TestTelemetrySettingsView):
    api_version = API_VERSION

    @override_settings(DEBUG=False, DEPLOYMENT_MODE="DUMMY_VALUE")
    def test_get_telemetry_settings_non_saas_non_debug(self):
        r = self.client.get(self.api_version_reverse("telemetry_settings"))
        self.assertEqual(r.status_code, HTTPStatus.NOT_IMPLEMENTED)

    @override_settings(DEBUG=False, DEPLOYMENT_MODE="DUMMY_VALUE")
    def test_set_telemetry_settings_non_saas_non_debug(self):
        r = self.client.post(self.api_version_reverse("telemetry_settings"))
        self.assertEqual(r.status_code, HTTPStatus.NOT_IMPLEMENTED)


class TestTelemetrySettingsViewAsNonSubscriberVersion1(TestTelemetrySettingsViewAsNonSubscriber):
    api_version = API_VERSION
