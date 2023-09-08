from http import HTTPStatus
from unittest.mock import patch

from ai.api.permissions import (
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
)
from ai.api.tests.test_views import WisdomServiceAPITestCaseBase
from django.urls import reverse


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
