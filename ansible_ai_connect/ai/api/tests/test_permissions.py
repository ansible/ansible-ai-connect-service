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
from unittest.mock import Mock, patch

from django.test import override_settings
from django.urls import reverse

from ansible_ai_connect.ai.api.permissions import (
    BlockUserWithoutSeat,
    BlockUserWithSeatButWCANotReady,
    BlockWCANotReadyButTrialAvailable,
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
)
from ansible_ai_connect.ai.api.tests.test_views import WisdomServiceAPITestCaseBaseOIDC
from ansible_ai_connect.test_utils import WisdomAppsBackendMocking
from ansible_ai_connect.users.models import Plan
from ansible_ai_connect.users.tests.test_users import create_user

CONTINUE = True
BLOCK = False


@patch.object(IsOrganisationAdministrator, "has_permission", return_value=False)
@patch.object(IsOrganisationLightspeedSubscriber, "has_permission", return_value=True)
class TestIfUserIsOrgAdministrator(WisdomServiceAPITestCaseBaseOIDC):
    def test_user_rh_user_is_org_admin(self, *args):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse("wca_api_key"))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
        self.assert_error_detail(
            r, IsOrganisationAdministrator.code, IsOrganisationAdministrator.message
        )


@patch.object(IsOrganisationAdministrator, "has_permission", return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, "has_permission", return_value=False)
class TestIfOrgIsLightspeedSubscriber(WisdomServiceAPITestCaseBaseOIDC):
    def test_user_is_lightspeed_subscriber_admin(self, *args):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse("wca_api_key"))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
        self.assert_error_detail(
            r, IsOrganisationLightspeedSubscriber.code, IsOrganisationLightspeedSubscriber.message
        )


@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
@override_settings(WCA_SECRET_DUMMY_SECRETS="")
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
        self.assertEqual(self.p.has_permission(self.request, None), CONTINUE)

    def test_non_seated_users_are_allowed(self):
        self.user.rh_user_has_seat = False
        self.assertEqual(self.p.has_permission(self.request, None), CONTINUE)

    def test_ensure_seated_user_are_blocked(self):
        self.user.rh_user_has_seat = True
        self.assertEqual(self.p.has_permission(self.request, None), BLOCK)

    @override_settings(ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL=True)
    def test_ensure_trial_user_can_pass_through(self):
        demo_plan, _ = Plan.objects.get_or_create(name="demo_90_days", expires_after="90 days")
        self.user.plans.add(demo_plan)
        self.assertEqual(self.p.has_permission(self.request, None), CONTINUE)


@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
@override_settings(WCA_SECRET_DUMMY_SECRETS="")
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

    def test_no_seat_users_are_not_allowed_without_tech_preview(self):
        self.assertEqual(self.p.has_permission(self.request, None), BLOCK)

    @override_settings(ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL=True)
    def test_ensure_trial_user_can_pass_through(self):
        demo_plan, _ = Plan.objects.get_or_create(name="demo_90_days", expires_after="90 days")
        self.user.plans.add(demo_plan)
        self.assertEqual(self.p.has_permission(self.request, None), CONTINUE)


@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
@override_settings(WCA_SECRET_DUMMY_SECRETS="")
@override_settings(ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL=True)
class TestBlockWCANotReadyButTrialAvailable(WisdomAppsBackendMocking):
    def setUp(self):
        super().setUp()
        self.user = create_user(provider="oidc")
        self.request = Mock()
        self.request.user = self.user
        self.p = BlockWCANotReadyButTrialAvailable()

    def tearDown(self):
        self.user.delete()
        super().tearDown()

    def test_non_redhat_users_are_allowed(self):
        self.user.organization = None
        self.assertEqual(self.p.has_permission(self.request, None), CONTINUE)

    def test_ensure_user_with_org_not_ready_are_blocked(self):
        self.user.rh_user_has_seat = True
        self.assertEqual(self.p.has_permission(self.request, None), BLOCK)

    @override_settings(ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL=False)
    def test_ensure_we_dont_block_user_if_feature_not_enabled(self):
        self.user.rh_user_has_seat = True
        self.assertEqual(self.p.has_permission(self.request, None), CONTINUE)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1234567:valid")
    def test_ensure_user_with_org_ready_are_accepted(self):
        self.user.rh_user_has_seat = True
        self.assertEqual(self.p.has_permission(self.request, None), CONTINUE)

    def test_ensure_trial_user_can_pass_through(self):
        demo_plan, _ = Plan.objects.get_or_create(name="demo_90_days", expires_after="90 days")
        self.user.plans.add(demo_plan)
        self.assertEqual(self.p.has_permission(self.request, None), CONTINUE)
