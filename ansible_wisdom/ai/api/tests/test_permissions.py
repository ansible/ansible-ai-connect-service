from http import HTTPStatus
from unittest.mock import patch

from django.urls import reverse

from ..permissions import (
    AcceptedTermsPermission,
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
    IsWCAKeyApiFeatureFlagOn,
)
from .test_views import WisdomServiceAPITestCaseBase


class AcceptedTermsPermissionTest(WisdomServiceAPITestCaseBase):
    payload = {
        "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
    }

    def accepted_terms(self):
        return patch.object(
            self.user,
            'community_terms_accepted',
            True,
        )

    def not_accepted_terms(self):
        return patch.object(
            self.user,
            'community_terms_accepted',
            None,
        )

    def test_community_user_has_not_accepted(self):
        with self.not_accepted_terms():
            self.client.force_authenticate(user=self.user)
            r = self.client.post(reverse('completions'), self.payload)
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)

    def test_commercial_user_has_not_accepted(self):
        self.user.has_seat = True
        with self.not_accepted_terms():
            self.client.force_authenticate(user=self.user)
            r = self.client.post(reverse('completions'), self.payload)
        self.assertNotEqual(r.status_code, HTTPStatus.FORBIDDEN)

    def test_community_user_has_accepted(self):
        with self.accepted_terms():
            self.client.force_authenticate(user=self.user)
            r = self.client.post(reverse('completions'), self.payload)
        self.assertNotEqual(r.status_code, HTTPStatus.FORBIDDEN)

    def test_commercial_user_has_accepted(self):
        self.user.has_seat = True
        with self.accepted_terms():
            self.client.force_authenticate(user=self.user)
            r = self.client.post(reverse('completions'), self.payload)
        self.assertNotEqual(r.status_code, HTTPStatus.FORBIDDEN)


@patch.object(IsOrganisationAdministrator, 'has_permission', return_value=False)
@patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=True)
@patch.object(IsWCAKeyApiFeatureFlagOn, 'has_permission', return_value=True)
class TestIfUserIsOrgAdministrator(WisdomServiceAPITestCaseBase):
    def test_user_rh_user_is_org_admin(self, *args):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_api_key'))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)


@patch.object(IsOrganisationAdministrator, 'has_permission', return_value=False)
@patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=False)
@patch.object(IsWCAKeyApiFeatureFlagOn, 'has_permission', return_value=True)
class TestIfOrgIsLightspeedSubscriber(WisdomServiceAPITestCaseBase):
    def test_user_is_lightspeed_subscriber_admin(self, *args):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_api_key'))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
