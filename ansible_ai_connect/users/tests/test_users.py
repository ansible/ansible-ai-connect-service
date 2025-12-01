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

import random
import string
from http import HTTPStatus
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from prometheus_client.parser import text_string_to_metric_families
from rest_framework.test import APITransactionTestCase

import ansible_ai_connect.ai.feature_flags as feature_flags
from ansible_ai_connect.ai.api.permissions import (
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
)
from ansible_ai_connect.organizations.models import ExternalOrganization
from ansible_ai_connect.test_utils import (
    APIVersionTestCaseBase,
    WisdomAppsBackendMocking,
    WisdomServiceLogAwareTestCase,
    create_user,
)
from ansible_ai_connect.users.constants import (
    USER_SOCIAL_AUTH_PROVIDER_AAP,
    USER_SOCIAL_AUTH_PROVIDER_GITHUB,
    USER_SOCIAL_AUTH_PROVIDER_OIDC,
)


@override_settings(DEPLOYMENT_MODE="upstream")
@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
@override_settings(SOCIAL_AUTH_GITHUB_TEAM_KEY="github-team-key")
class TestUsers(APIVersionTestCaseBase, APITransactionTestCase, WisdomServiceLogAwareTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.password = "somepassword"
        self.user = create_user(
            password=self.password,
            provider=USER_SOCIAL_AUTH_PROVIDER_GITHUB,
            external_username="anexternalusername",
        )
        cache.clear()

    def test_users(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(self.api_version_reverse("me"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertEqual(self.user.username, r.data.get("username"))

    def test_home_view(self):
        self.client.login(username=self.user.username, password=self.password)
        r = self.client.get(reverse("home"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertIn(self.user.external_username, str(r.content))

    def test_home_view_without_login(self):
        r = self.client.get(reverse("home"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertIn("You are currently not logged in.", str(r.content))

    def test_users_audit_logging(self):
        with self.assertLogs(logger="ansible_ai_connect.users.signals", level="INFO") as log:
            self.client.login(username=self.user.username, password=self.password)
            self.assertInLog("LOGIN successful", log)


@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
@override_settings(WCA_SECRET_DUMMY_SECRETS="1981:valid")
@override_settings(AUTHZ_BACKEND_TYPE="dummy")
@override_settings(AUTHZ_DUMMY_ORGS_WITH_SUBSCRIPTION="1981")
class TestUserSeat(WisdomAppsBackendMocking):
    def setUp(self) -> None:
        super().setUp()
        cache.clear()

    @override_settings(DEPLOYMENT_MODE="upstream")
    def test_rh_user_has_seat_with_no_rhsso_user(self):
        user = create_user(provider=USER_SOCIAL_AUTH_PROVIDER_GITHUB)
        self.assertFalse(user.rh_user_has_seat)

    @override_settings(DEPLOYMENT_MODE="saas")
    def test_rh_user_has_seat_with_rhsso_user_no_seat(self):
        user = create_user(provider=USER_SOCIAL_AUTH_PROVIDER_OIDC, username="not-seated")
        self.assertFalse(user.rh_user_has_seat)

    @override_settings(DEPLOYMENT_MODE="saas")
    def test_rh_user_has_seat_with_rhsso_user_with_seat(self):
        user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            rh_user_id="seated-user-id",
            rh_org_id=1981,
            external_username="seated",
        )
        self.assertTrue(user.rh_user_has_seat)

    @override_settings(DEPLOYMENT_MODE="saas")
    def test_rh_user_has_seat_with_no_seat_checker(self):
        with patch.object(apps.get_app_config("ai"), "get_seat_checker", lambda: None):
            user = create_user(provider=USER_SOCIAL_AUTH_PROVIDER_OIDC)
            self.assertFalse(user.rh_user_has_seat)

    @override_settings(DEPLOYMENT_MODE="saas")
    def test_rh_user_in_unlimited_org(self):
        user = create_user(provider=USER_SOCIAL_AUTH_PROVIDER_OIDC)
        org = ExternalOrganization(None, None)
        org.is_subscription_check_should_be_bypassed = True
        user.organization = org
        self.assertTrue(user.rh_org_has_subscription)

    @override_settings(DEPLOYMENT_MODE="saas")
    def test_rh_user_onprem_has_valid_license(self):
        user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC, social_auth_extra_data={"aap_licensed": True}
        )
        with patch.object(user, "is_aap_user") as return_true:
            return_true.return_value = True
            self.assertTrue(user.rh_org_has_subscription)

    @override_settings(DEPLOYMENT_MODE="saas")
    def test_rh_user_onprem_has_no_valid_license(self):
        user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC, social_auth_extra_data={"aap_licensed": False}
        )
        with patch.object(user, "is_aap_user") as return_true:
            return_true.return_value = True
            self.assertFalse(user.rh_org_has_subscription)

    @override_settings(DEPLOYMENT_MODE="saas")
    def test_rh_user_org_with_sub_but_no_seat_in_ams(self):
        user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            rh_user_id="seated-user-id",
            rh_org_id=1981,
            external_username="no-seated",
        )
        self.assertTrue(user.rh_user_has_seat)

    @override_settings(DEPLOYMENT_MODE="saas")
    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    @override_settings(WCA_SECRET_DUMMY_SECRETS="")
    def test_rh_user_org_with_sub_but_no_sec_and_tech_preview(self):
        user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            rh_user_id="seated-user-id",
            rh_org_id=1981,
            external_username="no-seated",
        )
        self.assertFalse(user.rh_user_has_seat)

    @override_settings(DEPLOYMENT_MODE="saas")
    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=False)
    @override_settings(WCA_SECRET_DUMMY_SECRETS="")
    def test_rh_user_org_with_sub_but_no_sec_after_tech_preview(self):
        user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            rh_user_id="seated-user-id",
            rh_org_id=1981,
            external_username="no-seated",
        )
        self.assertTrue(user.rh_user_has_seat)


class TestUsername(WisdomServiceLogAwareTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.local_user = create_user(
            username="local-user",
            password="bar",
        )

        self.sso_user = create_user(
            username="sso-user",
            password="bar",
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            external_username="babar",
        )
        cache.clear()

    def tearDown(self) -> None:
        self.local_user.delete()
        self.sso_user.delete()
        super().tearDown()

    def test_username_from_sso(self) -> None:
        self.assertEqual(self.sso_user.external_username, "babar")
        self.assertEqual(self.local_user.external_username, "")


@override_settings(AUTHZ_BACKEND_TYPE="dummy")
@override_settings(AUTHZ_DUMMY_ORGS_WITH_SUBSCRIPTION="1981")
class TestIsOrgLightspeedSubscriber(WisdomAppsBackendMocking):
    def setUp(self) -> None:
        super().setUp()
        cache.clear()

    def test_rh_org_has_subscription_with_no_rhsso_user(self):
        user = create_user(provider=USER_SOCIAL_AUTH_PROVIDER_GITHUB)
        self.assertFalse(user.rh_org_has_subscription)

    def test_rh_org_has_subscription_with_subscribed_user(self):
        user = create_user(provider=USER_SOCIAL_AUTH_PROVIDER_OIDC, rh_org_id=1981)
        self.assertTrue(user.rh_org_has_subscription)

    def test_rh_org_has_subscription_with_non_subscribed_user(self):
        user = create_user(provider=USER_SOCIAL_AUTH_PROVIDER_OIDC)
        self.assertFalse(user.rh_org_has_subscription)


@override_settings(AUTHZ_BACKEND_TYPE="dummy")
class TestThirdPartyAuthentication(
    APIVersionTestCaseBase, WisdomAppsBackendMocking, APITransactionTestCase
):
    def setUp(self) -> None:
        super().setUp()
        cache.clear()

    def test_github_user_external_username(self):
        external_username = "github_username"
        user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_GITHUB,
            external_username=external_username,
        )
        self.assertEqual(external_username, user.external_username)
        self.assertNotEqual(user.username, user.external_username)
        self.assertNotEqual(user.external_username, "")

    def test_rhsso_user_external_username(self):
        external_username = "sso_username"
        user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            external_username=external_username,
        )
        self.assertEqual(external_username, user.external_username)
        self.assertNotEqual(user.username, user.external_username)
        self.assertNotEqual(user.external_username, "")

    def test_github_user_login(self):
        external_username = "github_username"
        user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_GITHUB,
            external_username=external_username,
        )
        self.client.force_authenticate(user=user)
        r = self.client.get(self.api_version_reverse("me"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertEqual(external_username, r.data.get("external_username"))
        self.assertNotEqual(user.username, r.data.get("external_username"))

    def test_rhsso_user_login(self):
        external_username = "sso_username"
        user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            external_username=external_username,
        )
        self.client.force_authenticate(user=user)
        r = self.client.get(self.api_version_reverse("me"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertEqual(external_username, r.data.get("external_username"))
        self.assertNotEqual(user.username, r.data.get("external_username"))

    def test_user_login_with_same_usernames(self):
        external_username = "a_username"
        oidc_user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            external_username=external_username,
        )

        github_user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_GITHUB, external_username=external_username
        )

        self.client.force_authenticate(user=oidc_user)
        r = self.client.get(self.api_version_reverse("me"))
        self.assertEqual(external_username, r.data.get("external_username"))

        self.client.force_authenticate(user=github_user)
        r = self.client.get(self.api_version_reverse("me"))
        self.assertEqual(external_username, r.data.get("external_username"))

        self.assertNotEqual(oidc_user.username, github_user.username)
        self.assertEqual(oidc_user.external_username, github_user.external_username)


class TestUserModelMetrics(APITransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        cache.clear()

    def test_user_model_metrics(self):
        def get_user_count():
            r = self.client.get(reverse("prometheus-metrics"))
            for family in text_string_to_metric_families(r.content.decode()):
                for sample in family.samples:
                    if sample[0] == "django_model_inserts_total" and sample[1] == {"model": "user"}:
                        return sample[2]

        # Obtain the user count before creating a dummy user
        before = get_user_count()

        # Create a dummy user
        username = "u" + "".join(random.choices(string.digits, k=5))
        password = "secret"
        email = username + "@example.com"
        get_user_model().objects.create_user(
            username=username,
            email=email,
            password=password,
        )

        # Make sure that the user count incremented
        self.assertEqual(1, get_user_count() - before)


class TestTelemetryOptInOut(APIVersionTestCaseBase, APITransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        cache.clear()
        feature_flags.FeatureFlags.instance = None

    def test_github_user(self):
        user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_GITHUB,
            social_auth_extra_data={"login": "github_username"},
            external_username="github_username",
        )
        self.client.force_authenticate(user=user)
        r = self.client.get(self.api_version_reverse("me"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertTrue(r.data.get("org_telemetry_opt_out"))

    def test_aap_user(self):
        user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_AAP,
            social_auth_extra_data={"login": "aap_username"},
            external_username="aap_username",
        )
        self.client.force_authenticate(user=user)
        r = self.client.get(self.api_version_reverse("me"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertTrue(r.data.get("org_telemetry_opt_out"))

    def test_rhsso_user_with_telemetry_opted_in(self):
        user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            social_auth_extra_data={"login": "sso_username"},
            external_username="sso_username",
            org_opt_out=False,
        )
        self.client.force_authenticate(user=user)
        r = self.client.get(self.api_version_reverse("me"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertFalse(r.data.get("org_telemetry_opt_out"))

    @override_settings(LAUNCHDARKLY_SDK_KEY="dummy_key")
    @patch.object(feature_flags, "LDClient")
    def test_rhsso_user_with_telemetry_opted_out(self, LDClient):
        LDClient.return_value.variation.return_value = True
        user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            social_auth_extra_data={"login": "sso_username"},
            external_username="sso_username",
            org_opt_out=True,
        )
        self.client.force_authenticate(user=user)
        r = self.client.get(self.api_version_reverse("me"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertTrue(r.data.get("org_telemetry_opt_out"))

    @override_settings(LAUNCHDARKLY_SDK_KEY="dummy_key")
    @patch.object(IsOrganisationAdministrator, "has_permission", return_value=True)
    @patch.object(IsOrganisationLightspeedSubscriber, "has_permission", return_value=True)
    @patch.object(feature_flags, "LDClient")
    def test_rhsso_user_caching(self, LDClient, *args):
        LDClient.return_value.variation.return_value = True
        user = create_user(
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            social_auth_extra_data={"login": "sso_username"},
            external_username="sso_username",
        )
        self.client.force_authenticate(user=user)

        # Default is False
        r = self.client.get(self.api_version_reverse("me"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertFalse(r.data.get("org_telemetry_opt_out"))

        # Update to True
        r = self.client.post(
            self.api_version_reverse("telemetry_settings"),
            data='{ "optOut": "True" }',
            content_type="application/json",
        )
        self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)

        # Cached value should persist
        r = self.client.get(self.api_version_reverse("me"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertFalse(r.data.get("org_telemetry_opt_out"))

        # Emulate cache expiring
        cache.clear()

        # Cache should update
        r = self.client.get(self.api_version_reverse("me"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertTrue(r.data.get("org_telemetry_opt_out"))
