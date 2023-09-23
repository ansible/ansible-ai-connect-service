from http import HTTPStatus
from unittest.mock import patch

from ai.api.permissions import (
    AcceptedTermsPermission,
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
    IsWCAKeyApiFeatureFlagOn,
    IsWCAModelIdApiFeatureFlagOn,
)
from ai.api.tests.test_views import WisdomServiceAPITestCaseBase
from django.test import override_settings
from django.urls import resolve, reverse
from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
from rest_framework.permissions import IsAuthenticated


class TestConsoleView(WisdomServiceAPITestCaseBase):
    def test_authentication_error(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('console'))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @patch.object(IsWCAKeyApiFeatureFlagOn, 'has_permission', return_value=True)
    @patch.object(IsWCAModelIdApiFeatureFlagOn, 'has_permission', return_value=True)
    @patch.object(IsOrganisationAdministrator, 'has_permission', return_value=True)
    @patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=True)
    def test_get_when_authenticated(self, *args):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('console'))
        self.assertEqual(r.status_code, HTTPStatus.OK)

    # Mock Permissions not being satisfied
    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @patch.object(IsWCAKeyApiFeatureFlagOn, 'has_permission', return_value=False)
    @patch.object(IsWCAModelIdApiFeatureFlagOn, 'has_permission', return_value=False)
    @patch.object(IsOrganisationAdministrator, 'has_permission', return_value=False)
    @patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=False)
    def test_get_when_authenticated_missing_permission(self, *args):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('console'))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)

    def test_permission_classes(self, *args):
        url = reverse('console')
        view = resolve(url).func.view_class

        required_permissions = [
            IsWCAKeyApiFeatureFlagOn,
            IsWCAModelIdApiFeatureFlagOn,
            IsAuthenticated,
            IsAuthenticatedOrTokenHasScope,
            IsOrganisationAdministrator,
            IsOrganisationLightspeedSubscriber,
            AcceptedTermsPermission,
        ]
        self.assertEqual(len(view.permission_classes), len(required_permissions))
        for permission in required_permissions:
            self.assertTrue(permission in view.permission_classes)

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @patch.object(IsWCAKeyApiFeatureFlagOn, 'has_permission', return_value=True)
    @patch.object(IsWCAModelIdApiFeatureFlagOn, 'has_permission', return_value=True)
    @patch.object(IsOrganisationAdministrator, 'has_permission', return_value=True)
    @patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=True)
    def test_extra_data(self, *args):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse('console'))
        self.assertIsInstance(response.context_data, dict)
        context = response.context_data
        self.assertEqual(context['user_name'], self.user.username)
