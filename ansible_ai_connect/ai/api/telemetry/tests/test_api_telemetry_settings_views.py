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
from unittest.mock import patch

from django.db.utils import DatabaseError
from django.test import override_settings
from django.urls import resolve
from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
from rest_framework.permissions import IsAuthenticated

import ansible_ai_connect.ai.feature_flags as feature_flags
from ansible_ai_connect.ai.api.permissions import (
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
)
from ansible_ai_connect.ai.api.tests.test_views import WisdomServiceAPITestCaseBase
from ansible_ai_connect.organizations.models import ExternalOrganization
from ansible_ai_connect.test_utils import APIVersionTestCaseBase


@patch.object(IsOrganisationAdministrator, "has_permission", return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, "has_permission", return_value=True)
class TestTelemetrySettingsView(APIVersionTestCaseBase, WisdomServiceAPITestCaseBase):
    def setUp(self):
        super().setUp()
        feature_flags.FeatureFlags.instance = None

    def test_get_settings_authentication_error(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.get(self.api_version_reverse("telemetry_settings"))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    def test_permission_classes(self, *args):
        url = self.api_version_reverse("telemetry_settings")
        view = resolve(url).func.view_class

        required_permissions = [
            IsAuthenticated,
            IsAuthenticatedOrTokenHasScope,
            IsOrganisationAdministrator,
            IsOrganisationLightspeedSubscriber,
        ]
        self.assertEqual(len(view.permission_classes), len(required_permissions))
        for permission in required_permissions:
            self.assertTrue(permission in view.permission_classes)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_get_settings_without_org_id(self, *args):
        self.client.force_authenticate(user=self.user)

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(self.api_version_reverse("telemetry_settings"))
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assert_segment_log(log, "telemetrySettingsGet", None)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    @override_settings(LAUNCHDARKLY_SDK_KEY="dummy_key")
    @patch.object(feature_flags, "LDClient")
    def test_get_settings_when_undefined(self, LDClient, *args):
        LDClient.return_value.variation.return_value = True
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        self.client.force_authenticate(user=self.user)

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(self.api_version_reverse("telemetry_settings"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertFalse(r.data["optOut"])
            self.assert_segment_log(log, "telemetrySettingsGet", None, opt_out=False)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    @override_settings(LAUNCHDARKLY_SDK_KEY="dummy_key")
    @patch.object(feature_flags, "LDClient")
    def test_get_settings_when_defined(self, LDClient, *args):
        LDClient.return_value.variation.return_value = True
        self.user.organization = ExternalOrganization.objects.get_or_create(
            id=123, telemetry_opt_out=True
        )[0]
        self.client.force_authenticate(user=self.user)

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(self.api_version_reverse("telemetry_settings"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertTrue(r.data["optOut"])
            self.assert_segment_log(log, "telemetrySettingsGet", None, opt_out=True)

    def test_set_settings_authentication_error(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.post(self.api_version_reverse("telemetry_settings"))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_set_settings_without_org_id(self, *args):
        self.client.force_authenticate(user=self.user)

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(self.api_version_reverse("telemetry_settings"))
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assert_segment_log(log, "telemetrySettingsSet", None)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    @override_settings(LAUNCHDARKLY_SDK_KEY="dummy_key")
    @patch.object(feature_flags, "LDClient")
    def test_set_settings_with_valid_value(self, LDClient, *args):
        LDClient.return_value.variation.return_value = True
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        self.client.force_authenticate(user=self.user)
        # Settings should initially be False
        r = self.client.get(self.api_version_reverse("telemetry_settings"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertFalse(r.data["optOut"])

        # Set settings
        with self.assertLogs(logger="ansible_ai_connect.users.signals", level="DEBUG") as signals:
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(
                    self.api_version_reverse("telemetry_settings"),
                    data='{ "optOut": "True" }',
                    content_type="application/json",
                )
                self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)
                self.assert_segment_log(log, "telemetrySettingsSet", None, opt_out=True)

            # Check audit entry
            self.assertInLog(
                f"User: '{self.user}' set Telemetry settings for "
                f"Organisation '{self.user.organization.id}'",
                signals,
            )

        # Check Settings were stored
        r = self.client.get(self.api_version_reverse("telemetry_settings"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertTrue(r.data["optOut"])

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    @override_settings(LAUNCHDARKLY_SDK_KEY="dummy_key")
    @patch.object(feature_flags, "LDClient")
    def test_set_settings_throws_exception(self, LDClient, *args):
        LDClient.return_value.variation.return_value = True
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        self.client.force_authenticate(user=self.user)

        with patch("django.db.models.base.Model.save", side_effect=DatabaseError()):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(
                    self.api_version_reverse("telemetry_settings"),
                    data='{ "optOut": "False" }',
                    content_type="application/json",
                )
                self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
                self.assert_segment_log(log, "telemetrySettingsSet", "DatabaseError", opt_out=False)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    @override_settings(LAUNCHDARKLY_SDK_KEY="dummy_key")
    @patch.object(feature_flags, "LDClient")
    def test_set_settings_throws_validation_exception(self, LDClient, *args):
        LDClient.return_value.variation.return_value = True
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        self.client.force_authenticate(user=self.user)

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(
                self.api_version_reverse("telemetry_settings"),
                data='{ "unknown_json_field": "a-new-key" }',
                content_type="application/json",
            )
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assert_segment_log(log, "telemetrySettingsSet", "ValidationError", opt_out=False)


@patch.object(IsOrganisationAdministrator, "has_permission", return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, "has_permission", return_value=False)
class TestTelemetrySettingsViewAsNonSubscriber(
    APIVersionTestCaseBase, WisdomServiceAPITestCaseBase
):
    def test_get_settings_as_non_subscriber(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        self.client.force_authenticate(user=self.user)
        r = self.client.get(self.api_version_reverse("telemetry_settings"))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
