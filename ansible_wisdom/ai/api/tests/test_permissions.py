from http import HTTPStatus
from unittest.mock import Mock, patch

from django.test import override_settings
from django.urls import reverse

from ansible_wisdom.ai.api.permissions import (
    AcceptedTermsPermission,
    BlockUserWithoutSeat,
    BlockUserWithoutSeatAndWCAReadyOrg,
    BlockUserWithSeatButWCANotReady,
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
)
from ansible_wisdom.ai.api.tests.test_views import WisdomServiceAPITestCaseBase
from ansible_wisdom.test_utils import WisdomAppsBackendMocking
from ansible_wisdom.users.tests.test_users import create_user


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
        self.assert_error_detail(r, AcceptedTermsPermission.code, AcceptedTermsPermission.message)

    def test_commercial_user_has_not_accepted(self):
        self.user.rh_user_has_seat = True
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
        self.user.rh_user_has_seat = True
        with self.accepted_terms():
            self.client.force_authenticate(user=self.user)
            r = self.client.post(reverse('completions'), self.payload)
        self.assertNotEqual(r.status_code, HTTPStatus.FORBIDDEN)


@patch.object(IsOrganisationAdministrator, 'has_permission', return_value=False)
@patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=True)
class TestIfUserIsOrgAdministrator(WisdomServiceAPITestCaseBase):
    def test_user_rh_user_is_org_admin(self, *args):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_api_key'))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
        self.assert_error_detail(
            r, IsOrganisationAdministrator.code, IsOrganisationAdministrator.message
        )


@patch.object(IsOrganisationAdministrator, 'has_permission', return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=False)
class TestIfOrgIsLightspeedSubscriber(WisdomServiceAPITestCaseBase):
    def test_user_is_lightspeed_subscriber_admin(self, *args):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_api_key'))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
        self.assert_error_detail(
            r, IsOrganisationLightspeedSubscriber.code, IsOrganisationLightspeedSubscriber.message
        )


@override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
class TestAcceptedTermsPermission(WisdomAppsBackendMocking):
    def setUp(self):
        super().setUp()
        self.user = create_user(provider="oidc")
        self.request = Mock()
        self.request.user = self.user
        self.p = AcceptedTermsPermission()

    def tearDown(self):
        self.user.delete()
        super().tearDown()

    def test_ensure_community_user_with_no_tc_is_blocked(self):
        self.user.community_terms_accepted = False
        self.assertFalse(self.p.has_permission(self.request, None))

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=False)
    def test_ensure_community_user_with_no_tc_is_allowed_post_tech_preview(self):
        self.user.community_terms_accepted = False
        self.user.rh_user_has_seat = False
        self.assertTrue(self.p.has_permission(self.request, None))

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=False)
    def test_ensure_seated_user_with_no_tc_is_accepted_with_tech_preview(self):
        self.user.community_terms_accepted = False
        self.user.rh_user_has_seat = True
        self.assertTrue(self.p.has_permission(self.request, None))

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=False)
    def test_ensure_seated_user_with_no_tc_is_accepted_post_tech_preview(self):
        self.user.community_terms_accepted = False
        self.user.rh_user_has_seat = True
        self.assertTrue(self.p.has_permission(self.request, None))


@override_settings(WCA_SECRET_BACKEND_TYPE='dummy')
@override_settings(WCA_SECRET_DUMMY_SECRETS='1234567:valid')
class TestBlockUserWithoutSeatAndWCAReadyOrg(WisdomAppsBackendMocking):
    def setUp(self):
        super().setUp()
        self.user = create_user(provider="oidc")
        self.request = Mock()
        self.request.user = self.user
        self.p = BlockUserWithoutSeatAndWCAReadyOrg()

    def tearDown(self):
        self.user.delete()
        super().tearDown()

    def test_ensure_user_with_no_org_are_allowed(self):
        self.user.organization = None
        self.assertTrue(self.p.has_permission(self.request, None))

    def test_ensure_seated_user_are_allowed(self):
        self.user.rh_user_has_seat = True
        self.assertTrue(self.p.has_permission(self.request, None))

    def test_ensure_unseated_user_are_blocked(self):
        self.user.rh_user_has_seat = False
        self.assertFalse(self.p.has_permission(self.request, None))


@override_settings(WCA_SECRET_BACKEND_TYPE='dummy')
@override_settings(WCA_SECRET_DUMMY_SECRETS='')
class TestBlockUserWithSeatButWCANotReady(WisdomAppsBackendMocking):
    def setUp(self):
        super().setUp()
        self.user = create_user(provider="oidc")
        self.request = Mock()
        self.request.user = self.user
        self.p = BlockUserWithSeatButWCANotReady()

    def tearDown(self):
        self.user.delete()
        super().tearDown()

    def test_non_redhat_users_are_allowed(self):
        self.user.organization = None
        self.assertTrue(self.p.has_permission(self.request, None))

    def test_non_seated_users_are_allowed(self):
        self.user.rh_user_has_seat = False
        self.assertTrue(self.p.has_permission(self.request, None))

    def test_ensure_seated_user_are_blocked(self):
        self.user.rh_user_has_seat = True
        self.assertFalse(self.p.has_permission(self.request, None))


@override_settings(WCA_SECRET_BACKEND_TYPE='dummy')
@override_settings(WCA_SECRET_DUMMY_SECRETS='')
class TestBlockUserWithoutSeat(WisdomAppsBackendMocking):
    def setUp(self):
        super().setUp()
        self.user = create_user(provider="oidc")
        self.user.rh_user_has_seat = False
        self.request = Mock()
        self.request.user = self.user
        self.p = BlockUserWithoutSeat()

    def tearDown(self):
        self.user.delete()
        super().tearDown()

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    def test_no_seat_users_are_allowed_with_tech_preview(self):
        self.assertTrue(self.p.has_permission(self.request, None))

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=False)
    def test_no_seat_users_are_not_allowed_without_tech_preview(self):
        self.assertFalse(self.p.has_permission(self.request, None))
