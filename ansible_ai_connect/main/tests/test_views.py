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

from datetime import datetime, timezone
from http import HTTPStatus
from textwrap import dedent

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponseRedirect
from django.test import RequestFactory, TestCase, modify_settings, override_settings
from django.urls import reverse
from rest_framework.test import APITransactionTestCase

from ansible_ai_connect.main.settings.base import SOCIAL_AUTH_OIDC_KEY
from ansible_ai_connect.main.views import LoginView
from ansible_ai_connect.test_utils import create_user_with_provider
from ansible_ai_connect.users.constants import (
    USER_SOCIAL_AUTH_PROVIDER_AAP,
    USER_SOCIAL_AUTH_PROVIDER_GITHUB,
    USER_SOCIAL_AUTH_PROVIDER_OIDC,
)
from ansible_ai_connect.users.models import Plan


class LogoutTest(TestCase):
    def test_rht_sso_redirect(self):
        user = create_user_with_provider(provider=USER_SOCIAL_AUTH_PROVIDER_OIDC)
        self.client.force_login(user)

        response = self.client.get(reverse("logout"))
        self.assertEqual(
            response.url,
            "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid"
            "-connect/logout?post_logout_redirect_uri=http://testserver/"
            f"&client_id={SOCIAL_AUTH_OIDC_KEY}",
        )

    def test_gh_sso_redirect(self):
        user = create_user_with_provider(provider=USER_SOCIAL_AUTH_PROVIDER_GITHUB)
        self.client.force_login(user)

        response = self.client.get(reverse("logout"))
        self.assertEqual(response.url, "/")

    @override_settings(AAP_API_URL="http://aap/api")
    def test_aap_sso_redirect(self):
        user = create_user_with_provider(provider=USER_SOCIAL_AUTH_PROVIDER_AAP)
        self.client.force_login(user)

        response = self.client.get(reverse("logout"))
        self.assertEqual(response.url, "http://aap/api/logout/?next=http://testserver/")

    def test_logout_without_login(self):
        self.client.get(reverse("logout"))


class AlreadyAuth(TestCase):
    def test_login(self):
        request = RequestFactory().get("/login")
        request.user = AnonymousUser()
        response = LoginView.as_view()(request)
        response.render()
        contents = response.content.decode()
        self.assertIn("You are currently not logged in.", contents)
        self.assertIn("Log in with Red Hat", contents)

    @override_settings(DEPLOYMENT_MODE="onprem")
    def test_login_aap(self):
        request = RequestFactory().get("/login")
        request.user = AnonymousUser()
        response = LoginView.as_view()(request)
        response.render()
        contents = response.content.decode()
        self.assertIn("You are currently not logged in.", contents)
        self.assertIn("Log in with Ansible Automation Platform", contents)

    @override_settings(DEPLOYMENT_MODE="onprem")
    @override_settings(AAP_API_PROVIDER_NAME="Ansible Automation Controller")
    def test_login_aap_override_provider_name(self):
        request = RequestFactory().get("/login")
        request.user = AnonymousUser()
        response = LoginView.as_view()(request)
        response.render()
        contents = response.content.decode()
        self.assertIn("You are currently not logged in.", contents)
        self.assertIn("Log in with Ansible Automation Controller", contents)

    @override_settings(DEPLOYMENT_MODE="upstream")
    def test_login_django(self):
        request = RequestFactory().get("/login")
        request.user = AnonymousUser()
        response = LoginView.as_view()(request)
        response.render()
        contents = response.content.decode()
        self.assertIn("You are currently not logged in.", contents)
        self.assertIn("Login to the service", contents)

    def test_no_login_for_auth_user(self):
        class MockUser:
            is_authenticated = True

        request = RequestFactory().get("/login")
        request.user = MockUser()
        response = LoginView.as_view()(request)
        self.assertTrue(isinstance(response, HttpResponseRedirect))
        self.assertEqual(response.url, "/")


@override_settings(ALLOW_METRICS_FOR_ANONYMOUS_USERS=False)
class TestMetricsView(APITransactionTestCase):

    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user(
            username="a-user",
            password="a-password",
            email="email@email.com",
        )

    def tearDown(self):
        self.user.delete()

    @override_settings(ALLOW_METRICS_FOR_ANONYMOUS_USERS=True)
    def test_content_type_text(self):
        r = self.client.get(reverse("prometheus-metrics"), headers={"Accept": "text/plain"})
        self.assertEqual(r.status_code, HTTPStatus.OK)

    @override_settings(ALLOW_METRICS_FOR_ANONYMOUS_USERS=True)
    def test_content_type_json(self):
        r = self.client.get(reverse("prometheus-metrics"), headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, HTTPStatus.NOT_ACCEPTABLE)

    @override_settings(ALLOW_METRICS_FOR_ANONYMOUS_USERS=True)
    def test_anonymous_access(self):
        r = self.client.get(reverse("prometheus-metrics"))
        self.assertEqual(r.status_code, HTTPStatus.OK)

    def test_protected_access(self):
        r = self.client.get(reverse("prometheus-metrics"))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    def test_protected_access_aap_superuser(self):
        self.user.rh_aap_superuser = True

        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse("prometheus-metrics"))
        self.assertEqual(r.status_code, HTTPStatus.OK)

    def test_protected_access_aap_system_auditor(self):
        self.user.rh_aap_system_auditor = True

        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse("prometheus-metrics"))
        self.assertEqual(r.status_code, HTTPStatus.OK)


@modify_settings()
@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
class TestMarkdownMe(TestCase):
    def test_get_view(self):
        user = create_user_with_provider(provider=USER_SOCIAL_AUTH_PROVIDER_OIDC)
        self.client.force_login(user=user)

        r = self.client.get(reverse("me_summary"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Logged in as: test_user_name")

    @override_settings(ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL=True)
    def test_get_view_trial(self):
        user = create_user_with_provider(provider=USER_SOCIAL_AUTH_PROVIDER_OIDC)
        self.client.force_login(user=user)

        trial_plan, _ = Plan.objects.get_or_create(name="trial of 90 days", expires_after="90 days")
        user.plans.add(trial_plan)
        up = user.userplan_set.first()
        up.expired_at = datetime(2024, 10, 14, tzinfo=timezone.utc)
        up.save()
        user.userplan_set.first().expired_at = ""

        r = self.client.get(reverse("me_summary"))
        self.assertEqual(r.status_code, 200)
        content = r.json()["content"]
        expectation = """
        Logged in as: test_user_name<br>
        Plan: trial of 90 days<br>
        Expiration: 2024-10-14
        """
        self.assertEqual(dedent(expectation).strip(), content)

        user.delete()
        trial_plan.delete()
