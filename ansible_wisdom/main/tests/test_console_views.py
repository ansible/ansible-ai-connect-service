from http import HTTPStatus
from unittest.mock import patch

import ai.feature_flags as feature_flags
from ai.api.permissions import (
    AcceptedTermsPermission,
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
)
from ai.api.tests.test_views import WisdomServiceAPITestCaseBase
from django.test import override_settings
from django.urls import resolve, reverse
from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
from organizations.models import Organization
from rest_framework.permissions import IsAuthenticated


class TestConsoleView(WisdomServiceAPITestCaseBase):
    def setUp(self):
        super().setUp()
        feature_flags.FeatureFlags.instance = None

    def test_authentication_error(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('console'))
        self.assertEqual(r.status_code, HTTPStatus.FOUND)
        self.assertEqual(r.url, '/login')

    @patch.object(IsOrganisationAdministrator, 'has_permission', return_value=True)
    @patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=True)
    def test_get_when_authenticated(self, *args):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('console'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertEqual(r.template_name, ['console/console.html'])

    # Mock IsOrganisationAdministrator Permission not being satisfied
    @patch.object(IsOrganisationAdministrator, 'has_permission', return_value=False)
    @patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=True)
    def test_get_when_authenticated_missing_permission_administrator(self, *args):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('console'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertEqual(r.template_name, ['console/denied.html'])

    # Mock IsOrganisationLightspeedSubscriber Permission not being satisfied
    @patch.object(IsOrganisationAdministrator, 'has_permission', return_value=True)
    @patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=False)
    def test_get_when_authenticated_missing_permission_subscription(self, *args):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('console'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertEqual(r.template_name, ['console/denied.html'])

    def test_permission_classes(self, *args):
        url = reverse('console')
        view = resolve(url).func.view_class

        required_permissions = [
            IsAuthenticated,
            IsAuthenticatedOrTokenHasScope,
            AcceptedTermsPermission,
        ]
        self.assertEqual(len(view.permission_classes), len(required_permissions))
        for permission in required_permissions:
            self.assertTrue(permission in view.permission_classes)

    @patch.object(IsOrganisationAdministrator, 'has_permission', return_value=True)
    @patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=True)
    def test_extra_data(self, *args):
        self.user.organization = Organization.objects.get_or_create(id=123)[0]
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse('console'))
        self.assertIsInstance(response.context_data, dict)
        context = response.context_data
        self.assertEqual(context['user_name'], self.user.username)
        self.assertEqual(context['rh_org_has_subscription'], self.user.rh_org_has_subscription)

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @patch.object(feature_flags, 'LDClient')
    def test_extra_data_telemetry_feature_enabled(self, LDClient, *args):
        LDClient.return_value.variation.return_value = True
        self.user.organization = Organization.objects.get_or_create(id=123)[0]
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse('console'))
        self.assertIsInstance(response.context_data, dict)
        context = response.context_data
        # The default setting for tests is True
        self.assertTrue(context['telemetry_schema_2_enabled'])

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @patch.object(feature_flags, 'LDClient')
    def test_extra_data_telemetry__feature_disabled(self, LDClient, *args):
        LDClient.return_value.variation.return_value = False
        self.user.organization = Organization.objects.get_or_create(id=123, telemetry_opt_out=True)[
            0
        ]
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse('console'))
        self.assertIsInstance(response.context_data, dict)
        context = response.context_data
        self.assertFalse(context['telemetry_schema_2_enabled'])
