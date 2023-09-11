from http import HTTPStatus
from unittest.mock import patch

from django.apps import apps
from django.test import override_settings
from django.urls import reverse
from requests.exceptions import ReadTimeout

from ..permissions import (
    AcceptedTermsPermission,
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
    IsWCAKeyApiFeatureFlagOn,
)
from .test_views import WisdomServiceAPITestCaseBase


class AcceptedTermsPermissionTest(WisdomServiceAPITestCaseBase):
    def test_user_has_not_accepted(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
        }
        with patch.object(
            self.user,
            'community_terms_accepted',
            None,
        ):
            with patch.object(
                self.user,
                'commercial_terms_accepted',
                None,
            ):
                self.client.force_authenticate(user=self.user)
                r = self.client.post(reverse('completions'), payload)
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)


@patch.object(IsOrganisationAdministrator, 'has_permission', return_value=False)
@patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=True)
@patch.object(IsWCAKeyApiFeatureFlagOn, 'has_permission', return_value=True)
@patch.object(AcceptedTermsPermission, 'has_permission', return_value=True)
class TestIfUserIsOrgAdministrator(WisdomServiceAPITestCaseBase):
    def test_user_rh_user_is_org_admin(self, *args):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_api_key'))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)


@patch.object(IsOrganisationAdministrator, 'has_permission', return_value=False)
@patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=False)
@patch.object(IsWCAKeyApiFeatureFlagOn, 'has_permission', return_value=True)
@patch.object(AcceptedTermsPermission, 'has_permission', return_value=True)
class TestIfOrgIsLightspeedSubsccriber(WisdomServiceAPITestCaseBase):
    def test_user_is_lightspeed_subscriber_admin(self, *args):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_api_key'))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
