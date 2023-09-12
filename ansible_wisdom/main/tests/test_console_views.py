from http import HTTPStatus
from unittest.mock import patch

from ai.api.permissions import (
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
    IsWCAKeyApiFeatureFlagOn,
    IsWCAModelIdApiFeatureFlagOn,
)
from ai.api.tests.test_views import WisdomServiceAPITestCaseBase
from django.test import override_settings
from django.urls import reverse


@override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
@patch.object(IsWCAKeyApiFeatureFlagOn, 'has_permission', return_value=True)
@patch.object(IsWCAModelIdApiFeatureFlagOn, 'has_permission', return_value=True)
@patch.object(IsOrganisationAdministrator, 'has_permission', return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=True)
class TestConsoleView(WisdomServiceAPITestCaseBase):
    def test_authentication_error(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('console'))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)

    def test_get_when_authenticated(self, *args):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('console'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
