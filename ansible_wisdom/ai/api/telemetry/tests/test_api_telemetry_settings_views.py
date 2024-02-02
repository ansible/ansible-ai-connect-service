from http import HTTPStatus
from unittest.mock import patch

from ai.api.permissions import (
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
)
from ai.api.tests.test_views import WisdomServiceAPITestCaseBase
from django.db.utils import DatabaseError
from django.test import override_settings
from django.urls import resolve, reverse
from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
from organizations.models import Organization
from rest_framework.permissions import IsAuthenticated


@patch.object(IsOrganisationAdministrator, 'has_permission', return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=True)
class TestTelemetrySettingsView(WisdomServiceAPITestCaseBase):
    def test_get_settings_authentication_error(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('telemetry_settings'))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    def test_permission_classes(self, *args):
        url = reverse('telemetry_settings')
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

    @override_settings(TELEMETRY_SCHEMA_2_ENABLED=False)
    def test_get_settings_when_feature_disabled(self, *args):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('telemetry_settings'))
        self.assertEqual(r.status_code, HTTPStatus.SERVICE_UNAVAILABLE)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_get_settings_without_org_id(self, *args):
        self.client.force_authenticate(user=self.user)

        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.get(reverse('telemetry_settings'))
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assert_segment_log(log, "telemetrySettingsGet", None)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_get_settings_when_undefined(self, *args):
        self.user.organization = Organization.objects.get_or_create(id=123)[0]
        self.client.force_authenticate(user=self.user)

        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.get(reverse('telemetry_settings'))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertFalse(r.data['optOut'])
            self.assert_segment_log(log, "telemetrySettingsGet", None, opt_out=False)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_get_settings_when_defined(self, *args):
        self.user.organization = Organization.objects.get_or_create(id=123, telemetry_opt_out=True)[
            0
        ]
        self.client.force_authenticate(user=self.user)

        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.get(reverse('telemetry_settings'))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertTrue(r.data['optOut'])
            self.assert_segment_log(log, "telemetrySettingsGet", None, opt_out=True)

    def test_set_settings_authentication_error(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.post(reverse('telemetry_settings'))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    @override_settings(TELEMETRY_SCHEMA_2_ENABLED=False)
    def test_set_settings_when_feature_disabled(self, *args):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('telemetry_settings'))
        self.assertEqual(r.status_code, HTTPStatus.SERVICE_UNAVAILABLE)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_set_settings_without_org_id(self, *args):
        self.client.force_authenticate(user=self.user)

        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(reverse('telemetry_settings'))
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assert_segment_log(log, "telemetrySettingsSet", None)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_set_settings_with_valid_value(self, *args):
        self.user.organization = Organization.objects.get_or_create(id=123)[0]
        self.client.force_authenticate(user=self.user)

        # Settings should initially be False
        r = self.client.get(reverse('telemetry_settings'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertFalse(r.data['optOut'])

        # Set settings
        with self.assertLogs(logger='users.signals', level='DEBUG') as signals:
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(
                    reverse('telemetry_settings'),
                    data='{ "optOut": "True" }',
                    content_type='application/json',
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
        r = self.client.get(reverse('telemetry_settings'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertTrue(r.data['optOut'])

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_set_settings_throws_exception(self, *args):
        self.user.organization = Organization.objects.get_or_create(id=123)[0]
        self.client.force_authenticate(user=self.user)

        with patch("django.db.models.base.Model.save", side_effect=DatabaseError()):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(
                    reverse('telemetry_settings'),
                    data='{ "optOut": "False" }',
                    content_type='application/json',
                )
                self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
                self.assert_segment_log(log, "telemetrySettingsSet", "DatabaseError", opt_out=False)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_set_settings_throws_validation_exception(self, *args):
        self.user.organization = Organization.objects.get_or_create(id=123)[0]
        self.client.force_authenticate(user=self.user)

        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(
                reverse('telemetry_settings'),
                data='{ "unknown_json_field": "a-new-key" }',
                content_type='application/json',
            )
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assert_segment_log(log, "telemetrySettingsSet", "ValidationError", opt_out=False)


@patch.object(IsOrganisationAdministrator, 'has_permission', return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=False)
class TestTelemetrySettingsViewAsNonSubscriber(WisdomServiceAPITestCaseBase):
    def test_get_settings_as_non_subscriber(self, *args):
        self.user.organization = Organization.objects.get_or_create(id=123)[0]
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('telemetry_settings'))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
