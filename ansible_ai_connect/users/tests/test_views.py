#!/usr/bin/env python3

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
from unittest.mock import ANY, Mock, patch

import boto3
from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APITransactionTestCase

import ansible_ai_connect.users.models
from ansible_ai_connect.main.tests.test_views import create_user_with_provider
from ansible_ai_connect.test_utils import WisdomAppsBackendMocking, create_user
from ansible_ai_connect.users.constants import (
    TRIAL_PLAN_NAME,
    USER_SOCIAL_AUTH_PROVIDER_GITHUB,
    USER_SOCIAL_AUTH_PROVIDER_OIDC,
)
from ansible_ai_connect.users.models import Plan


def bypass_init(*args, **kwargs):
    return None


@override_settings(ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL=False)
@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
@patch.object(boto3, "client", Mock())
class UserHomeTestAsAnonymous(WisdomAppsBackendMocking, TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()

    def test_unauthorized(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please log in using the button below.", count=1)
        self.assertNotContains(response, "Role:")
        self.assertNotContains(response, "Admin Portal")

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    def test_unauthorized_with_tech_preview(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, "Log in to Tech Preview")

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=False)
    def test_unauthorized_without_tech_preview(self):
        response = self.client.get(reverse("login"))
        self.assertNotContains(response, "Log in to Tech Preview")


@override_settings(ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL=False)
@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
@override_settings(WCA_SECRET_DUMMY_SECRETS="")
class UserHomeTestAsAdmin(WisdomAppsBackendMocking, TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.user = create_user(provider="oidc", rh_user_is_org_admin=True)
        self.client.force_login(self.user)

    def tearDown(self):
        self.user.delete()
        super().tearDown()

    @patch.object(ansible_ai_connect.users.models.User, "rh_org_has_subscription", True)
    @patch.object(ansible_ai_connect.users.models.User, "rh_user_has_seat", True)
    def test_rh_admin_with_seat_and_no_secret(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Role: administrator, licensed user")
        self.assertContains(response, "pf-c-alert__title", count=1)
        self.assertContains(response, "model settings have not been configured", count=1)
        self.assertContains(response, "Admin Portal", count=1)

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    @override_settings(ANSIBLE_AI_PROJECT_NAME="Project Name")
    @patch.object(ansible_ai_connect.users.models.User, "rh_org_has_subscription", False)
    @patch.object(ansible_ai_connect.users.models.User, "rh_user_has_seat", False)
    def test_rh_admin_without_seat_and_with_no_secret_with_tech_preview(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pf-c-alert__title", count=1)
        self.assertNotContains(response, "Your organization doesn't have access to Project Name.")
        self.assertNotContains(response, "You will be limited to features of the Project Name")
        self.assertNotContains(
            response, "The Project Name Technical Preview is no longer available"
        )
        self.assertContains(response, "Role: administrator")
        self.assertContains(response, "Admin Portal")

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=False)
    @override_settings(ANSIBLE_AI_PROJECT_NAME="Project Name")
    @patch.object(ansible_ai_connect.users.models.User, "rh_org_has_subscription", False)
    @patch.object(ansible_ai_connect.users.models.User, "rh_user_has_seat", False)
    def test_rh_admin_without_seat_and_with_no_secret_no_sub_without_tech_preview(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your organization doesn't have access to Project Name.")
        self.assertContains(
            response,
            "You do not have an Active subscription to Ansible Automation Platform "
            "which is required to use Project Name.",
        )
        self.assertContains(response, "Role: administrator")
        self.assertContains(response, "Admin Portal")

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1234567:valid")
    @patch.object(ansible_ai_connect.users.models.User, "rh_org_has_subscription", True)
    @patch.object(ansible_ai_connect.users.models.User, "rh_user_has_seat", True)
    def test_rh_admin_with_a_seat_and_with_secret(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Role: administrator, licensed user")
        self.assertContains(response, "Admin Portal")


@override_settings(ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL=False)
@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
@override_settings(WCA_SECRET_DUMMY_SECRETS="")
@patch.object(boto3, "client", Mock())
class UserHomeTestAsUser(WisdomAppsBackendMocking, TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.user = create_user(provider="oidc", rh_user_is_org_admin=False)
        self.client.force_login(self.user)

    def tearDown(self):
        self.user.delete()
        super().tearDown()

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    @override_settings(ANSIBLE_AI_PROJECT_NAME="Project Name")
    @override_settings(WCA_SECRET_DUMMY_SECRETS="")
    @patch.object(ansible_ai_connect.users.models.User, "rh_org_has_subscription", True)
    @patch.object(ansible_ai_connect.users.models.User, "rh_user_has_seat", False)
    def test_rh_user_without_seat_and_no_secret_with_tech_preview(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Role:")
        self.assertContains(response, "pf-c-alert__title", count=2)
        self.assertContains(response, "You do not have a licensed seat for Project Name")
        self.assertContains(response, "You will be limited to features of the Project Name")
        self.assertNotContains(response, "fas fa-exclamation-circle")
        self.assertNotContains(response, "Admin Portal")
        self.assertNotContains(
            response, "The Project Name Technical Preview is no longer available"
        )

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    @override_settings(ANSIBLE_AI_PROJECT_NAME="Project Name")
    @override_settings(WCA_SECRET_DUMMY_SECRETS="valid")
    @patch.object(ansible_ai_connect.users.models.User, "rh_org_has_subscription", True)
    @patch.object(ansible_ai_connect.users.models.User, "rh_user_has_seat", False)
    def test_rh_user_without_seat_with_secret_with_tech_preview(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Role:")
        self.assertContains(response, "pf-c-alert__title", count=2)
        self.assertContains(response, "You do not have a licensed seat for Project Name")
        self.assertContains(response, "You will be limited to features of the Project Name")
        self.assertNotContains(response, "fas fa-exclamation-circle")
        self.assertNotContains(response, "Admin Portal")
        self.assertNotContains(
            response, "The Project Name Technical Preview is no longer available"
        )

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=False)
    @override_settings(ANSIBLE_AI_PROJECT_NAME="Project Name")
    @override_settings(WCA_SECRET_DUMMY_SECRETS="")
    @patch.object(ansible_ai_connect.users.models.User, "rh_org_has_subscription", True)
    @patch.object(ansible_ai_connect.users.models.User, "rh_user_has_seat", False)
    def test_rh_user_without_seat_and_no_secret_without_tech_preview(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Role:")
        self.assertContains(response, "You do not have a licensed seat for Project Name")
        self.assertNotContains(response, "You will be limited to features of the Project Name")
        self.assertNotContains(response, "Admin Portal")

    @override_settings(WCA_SECRET_DUMMY_SECRETS="")
    @patch.object(ansible_ai_connect.users.models.User, "rh_org_has_subscription", True)
    @patch.object(ansible_ai_connect.users.models.User, "rh_user_has_seat", True)
    def test_rh_user_with_a_seat_and_no_secret(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Role: licensed user")
        self.assertContains(response, "but your administrator has not configured the service")
        self.assertNotContains(response, "Admin Portal")

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1234567:valid")
    @override_settings(ANSIBLE_AI_PROJECT_NAME="Project Name")
    @patch.object(ansible_ai_connect.users.models.User, "rh_org_has_subscription", True)
    @patch.object(ansible_ai_connect.users.models.User, "rh_user_has_seat", True)
    def test_rh_user_with_a_seat_and_with_secret(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Role: licensed user")
        self.assertContains(response, "Project Name</h1>")
        self.assertNotContains(response, "Admin Portal")

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    @override_settings(WCA_SECRET_DUMMY_SECRETS="1234567:valid")
    @patch.object(ansible_ai_connect.users.models.User, "rh_org_has_subscription", True)
    @patch.object(ansible_ai_connect.users.models.User, "rh_user_has_seat", False)
    def test_rh_user_with_no_seat_and_with_secret(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Role: licensed user")
        self.assertNotContains(response, "more information on how to get a licensed seat.")
        self.assertContains(response, "pf-c-alert__title", count=2)
        self.assertNotContains(response, "Admin Portal")

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=False)
    @override_settings(ANSIBLE_AI_PROJECT_NAME="Project Name")
    @patch.object(ansible_ai_connect.users.models.User, "rh_org_has_subscription", False)
    @patch.object(ansible_ai_connect.users.models.User, "rh_user_has_seat", False)
    def test_user_without_seat_and_with_secret_without_tech_preview(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your organization doesn't have access to Project Name.")
        self.assertContains(
            response, "Contact your Red Hat Organization's administrator for more information."
        )
        self.assertContains(response, "fa-exclamation-circle")


@override_settings(ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL=False)
@override_settings(AUTHZ_BACKEND_TYPE="dummy")
class TestHomeDocumentationUrl(WisdomAppsBackendMocking, APITransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.password = "somepassword"

    @override_settings(COMMERCIAL_DOCUMENTATION_URL="https://official_docs")
    @patch.object(ansible_ai_connect.users.models.User, "rh_user_has_seat", True)
    def test_docs_url_for_seated_user(self):
        self.user = create_user(
            password=self.password,
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
        )
        self.client.login(username=self.user.username, password=self.password)
        r = self.client.get(reverse("home"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertIn("https://official_docs", str(r.content))

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=False)
    @override_settings(ANSIBLE_AI_PROJECT_NAME="Project Name")
    @patch.object(ansible_ai_connect.users.models.User, "rh_user_has_seat", False)
    def test_docs_url_for_unseated_user_without_tech_preview(self):
        self.user = create_user(
            password=self.password,
            provider=USER_SOCIAL_AUTH_PROVIDER_GITHUB,
        )
        self.client.login(username=self.user.username, password=self.password)
        r = self.client.get(reverse("home"))
        self.assertContains(r, "Your organization doesn't have access to Project Name.")
        self.assertIn(settings.COMMERCIAL_DOCUMENTATION_URL, str(r.content))

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=False)
    def test_docs_url_for_not_logged_in_user_without_tech_preview(self):
        r = self.client.get(reverse("home"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertIn(settings.COMMERCIAL_DOCUMENTATION_URL, str(r.content))


@override_settings(ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL=True)
@override_settings(AUTHZ_BACKEND_TYPE="dummy")
@override_settings(AUTHZ_DUMMY_ORGS_WITH_SUBSCRIPTION="*")
@override_settings(WCA_SECRET_DUMMY_SECRETS="")
class TestTrial(WisdomAppsBackendMocking, APITransactionTestCase):
    def setUp(self):
        super().setUp()
        self.patcher = patch("ansible_ai_connect.ai.api.utils.segment.base_send_segment_event")
        self.m_base_send_segment_event = self.patcher.start()
        self.user = create_user_with_provider(provider=USER_SOCIAL_AUTH_PROVIDER_OIDC)
        self.client.force_login(self.user)

    def tearDown(self):
        super().tearDown()
        self.patcher.stop()
        self.user.delete()

    def test_redirect(self):
        r = self.client.get(reverse("home"))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, "/trial/")

    @override_settings(AUTHZ_DUMMY_ORGS_WITH_SUBSCRIPTION="")
    def test_no_aap_subscription__no_trial_for_you(self):
        r = self.client.get(reverse("trial"))
        self.assertEqual(r.status_code, 403)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1234567:valid")
    def test_wca_ready_org__no_trial_for_you(self):
        self.assertEqual(self.user.organization.id, 1234567)
        r = self.client.get(reverse("trial"))
        self.assertEqual(r.status_code, 403)

    def test_redirect_when_admin(self):
        self.user.rh_user_is_org_admin = True
        self.user.save()
        r = self.client.get(reverse("home"))
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Start a [90] days free trial", str(r.content))

    def test_accept_trial_terms(self):
        self.client.get(reverse("trial"))
        r = self.client.post(
            reverse("trial"),
            data={"accept_trial_terms": "True"},
        )
        self.assertNotIn("Information alert", str(r.content))
        self.assertIn('accept_trial_terms" checked', str(r.content))

    def test_accept_marketing_emails(self):
        self.client.get(reverse("trial"))
        r = self.client.post(
            reverse("trial"),
            data={
                "accept_marketing_emails": "True",
                "accept_trial_terms": "True",
                "start_trial_button": "True",
            },
        )

        self.assertNotIn("Information alert", str(r.content))
        self.assertIn('accept_marketing_emails" checked', str(r.content))

    def test_set_db_marketing_value(self):
        self.client.get(reverse("trial"))
        self.client.post(
            reverse("trial"),
            data={
                "accept_trial_terms": "on",
                "accept_marketing_emails": "on",
                "start_trial_button": "True",
            },
        )

        self.assertTrue(self.user.userplan_set.first().accept_marketing)

    def test_try_to_create_two_trial_records(self):
        self.client.get(reverse("trial"))
        for _ in range(2):
            self.client.post(
                reverse("trial"),
                data={
                    "accept_trial_terms": "on",
                    "start_trial_button": "True",
                },
            )

        self.assertEqual(self.user.userplan_set.all().count(), 1)

    def test_accept_trial_without_terms(self):
        self.client.get(reverse("trial"))
        r = self.client.post(
            reverse("trial"),
            data={
                "start_trial_button": "True",
            },
        )
        self.assertNotIn('accept_trial_terms" checked', str(r.content))
        self.assertIn("Terms and Conditions Information alert", str(r.content))

    def test_accept_trial_without_either(self):
        self.client.get(reverse("trial"))
        r = self.client.post(
            reverse("trial"),
            data={
                "start_trial_button": "True",
            },
        )
        self.assertNotIn('accept_trial_terms" checked', str(r.content))
        self.assertNotIn('allow_information_share" checked', str(r.content))
        self.assertIn("Terms and Conditions Information alert", str(r.content))

    def test_accept_trial(self):
        self.client.get(reverse("trial"))
        r = self.client.post(
            reverse("trial"),
            data={
                "accept_trial_terms": "on",
                "allow_information_share": "on",
                "start_trial_button": "True",
            },
        )
        self.assertContains(r, "You have 89 days left")

        self.assertEqual(self.user.plans.first().name, TRIAL_PLAN_NAME)
        self.assertTrue(self.user.userplan_set.first().expired_at)

    def test_trial_period_is_done(self):
        trial_plan, _ = Plan.objects.get_or_create(
            name="trial of -10 days", expires_after="-10 days"
        )
        self.user.plans.add(trial_plan)
        r = self.client.get(reverse("trial"))
        self.assertContains(r, "Your trial period has expired")

    @override_settings(SEGMENT_WRITE_KEY="blablabla")
    def test_accept_trial_schema1(self):
        self.client.get(reverse("trial"))
        self.client.post(
            reverse("trial"),
            data={
                "accept_marketing_emails": "on",
                "accept_trial_terms": "on",
                "allow_information_share": "on",
                "start_trial_button": "True",
            },
        )

        schema1_payload = self.m_base_send_segment_event.call_args_list[0].args[0]
        del schema1_payload["plans"][0]["created_at"]
        del schema1_payload["plans"][0]["expired_at"]
        expected = {
            "imageTags": "image-tags-not-defined",
            "groups": [],
            "rh_user_has_seat": True,
            "rh_user_org_id": 1234567,
            "modelName": "",
            "problem": "",
            "exception": False,
            "request": {"method": "POST", "path": "/trial/"},
            "plans": [
                {
                    "accept_marketing": True,
                    "is_active": True,
                    "name": "trial of 90 days",
                    "plan_id": self.user.plans.first().id,
                }
            ],
        }
        for k, v in expected.items():
            self.assertEqual(v, schema1_payload[k])

        self.m_base_send_segment_event.assert_called_with(
            ANY, "oneClickTrialStarted", self.user, ANY
        )

    @override_settings(ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL=False)
    def test_no_trial_for_you(self):
        r = self.client.get(reverse("home"))
        self.assertEqual(r.status_code, 200)  # No redirect
        r = self.client.get(reverse("trial"))
        self.assertEqual(r.status_code, 403)
