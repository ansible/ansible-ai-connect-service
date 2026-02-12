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

from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from textwrap import dedent
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.http import HttpResponseRedirect
from django.test import RequestFactory, TestCase, modify_settings, override_settings
from django.urls import reverse
from rest_framework.test import APITransactionTestCase

from ansible_ai_connect.ai.api.model_pipelines.nop.configuration import NopConfiguration
from ansible_ai_connect.ai.api.model_pipelines.nop.pipelines import (
    NopChatBotPipeline,
    NopStreamingChatBotPipeline,
)
from ansible_ai_connect.main.settings.base import SOCIAL_AUTH_OIDC_KEY
from ansible_ai_connect.main.views import LoginView
from ansible_ai_connect.organizations.models import Organization
from ansible_ai_connect.test_utils import (
    APIVersionTestCaseBase,
    create_user_with_provider,
)
from ansible_ai_connect.users.constants import (
    TRIAL_PLAN_NAME,
    USER_SOCIAL_AUTH_PROVIDER_AAP,
    USER_SOCIAL_AUTH_PROVIDER_GITHUB,
    USER_SOCIAL_AUTH_PROVIDER_OIDC,
)
from ansible_ai_connect.users.models import Plan


class LogoutTest(TestCase):
    def test_rht_sso_redirect(self):
        user = create_user_with_provider(provider=USER_SOCIAL_AUTH_PROVIDER_OIDC)
        self.client.force_login(user)

        response = self.client.post(reverse("logout"))
        self.assertEqual(
            response.url,
            "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid"
            "-connect/logout?post_logout_redirect_uri=http://testserver/"
            f"&client_id={SOCIAL_AUTH_OIDC_KEY}",
        )

    def test_gh_sso_redirect(self):
        user = create_user_with_provider(provider=USER_SOCIAL_AUTH_PROVIDER_GITHUB)
        self.client.force_login(user)

        response = self.client.post(reverse("logout"))
        self.assertEqual(response.url, "/")

    @override_settings(AAP_API_URL="http://aap/api")
    def test_aap_sso_redirect(self):
        user = create_user_with_provider(provider=USER_SOCIAL_AUTH_PROVIDER_AAP)
        self.client.force_login(user)

        response = self.client.post(reverse("logout"))
        self.assertEqual(response.url, "http://aap/api/logout/?next=http://testserver/")

    def test_logout_without_login(self):
        self.client.post(reverse("logout"))


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

    def test_no_login_for_auth_user_with_next(self):
        class MockUser:
            is_authenticated = True

        request = RequestFactory().get("/login?next=/chatbot", SERVER_NAME="testserver")
        request.user = MockUser()
        response = LoginView.as_view()(request)
        self.assertTrue(isinstance(response, HttpResponseRedirect))
        self.assertEqual(response.url, "/chatbot")

    def test_no_login_for_auth_user_with_unsafe_next(self):
        class MockUser:
            is_authenticated = True

        request = RequestFactory().get("/login?next=http://malicious-site.com")
        request.user = MockUser()
        response = LoginView.as_view()(request)
        self.assertTrue(isinstance(response, HttpResponseRedirect))
        self.assertEqual(response.url, "/")


class LoginViewProjectNameTest(TestCase):
    @override_settings(ANSIBLE_AI_PROJECT_NAME="Ansible Lightspeed with IBM watsonx Code Assistant")
    def test_project_name_unchanged_without_next(self):
        request = RequestFactory().get("/login")
        request.user = AnonymousUser()
        response = LoginView.as_view()(request)
        response.render()
        contents = response.content.decode()
        self.assertIn("Log in to Ansible Lightspeed with IBM watsonx Code Assistant", contents)

    @override_settings(ANSIBLE_AI_PROJECT_NAME="Ansible Lightspeed with IBM watsonx Code Assistant")
    def test_project_name_unchanged_with_different_next(self):
        request = RequestFactory().get("/login?next=/home")
        request.user = AnonymousUser()
        response = LoginView.as_view()(request)
        response.render()
        contents = response.content.decode()
        self.assertIn("Log in to Ansible Lightspeed with IBM watsonx Code Assistant", contents)

    @override_settings(ANSIBLE_AI_PROJECT_NAME="Ansible Lightspeed with IBM watsonx Code Assistant")
    def test_project_name_modified_with_chatbot_next(self):
        request = RequestFactory().get("/login?next=/chatbot")
        request.user = AnonymousUser()
        response = LoginView.as_view()(request)
        response.render()
        contents = response.content.decode()
        self.assertIn("Log in to Ansible Lightspeed", contents)
        self.assertNotIn("Log in to Ansible Lightspeed with IBM watsonx Code Assistant", contents)

    @override_settings(ANSIBLE_AI_PROJECT_NAME="Ansible Lightspeed with IBM watsonx Code Assistant")
    def test_project_name_modified_with_chatbot_slash_next(self):
        request = RequestFactory().get("/login?next=/chatbot/")
        request.user = AnonymousUser()
        response = LoginView.as_view()(request)
        response.render()
        contents = response.content.decode()
        self.assertIn("Log in to Ansible Lightspeed", contents)
        self.assertNotIn("Log in to Ansible Lightspeed with IBM watsonx Code Assistant", contents)

    @override_settings(ANSIBLE_AI_PROJECT_NAME="Ansible AI Connect")
    def test_project_name_no_change_if_no_watsonx_text(self):
        request = RequestFactory().get("/login?next=/chatbot")
        request.user = AnonymousUser()
        response = LoginView.as_view()(request)
        response.render()
        contents = response.content.decode()
        self.assertIn("Log in to Ansible AI Connect", contents)


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
class TestMarkdownMe(APIVersionTestCaseBase, TestCase):
    def test_get_view(self):
        user = create_user_with_provider(provider=USER_SOCIAL_AUTH_PROVIDER_OIDC)
        self.client.force_login(user=user)

        r = self.client.get(self.api_version_reverse("me_summary"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Logged in as: test_user_name")

    @override_settings(ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL=True)
    @override_settings(AUTHZ_DUMMY_ORGS_WITH_SUBSCRIPTION="*")
    def test_get_view_trial(self):
        user = create_user_with_provider(provider=USER_SOCIAL_AUTH_PROVIDER_OIDC)
        self.client.force_login(user=user)

        trial_plan, _ = Plan.objects.get_or_create(name=TRIAL_PLAN_NAME, expires_after="90 days")
        user.plans.add(trial_plan)
        up = user.userplan_set.first()
        up.expired_at = datetime.now(timezone.utc) + timedelta(days=90)
        up.save()
        user.userplan_set.first().expired_at = ""

        r = self.client.get(self.api_version_reverse("me_summary"))
        self.assertEqual(r.status_code, 200)
        content = r.json()["content"]
        expired_at = up.expired_at.strftime("%Y-%m-%d")
        expectation = f"""
        Logged in as: test_user_name<br>
        Plan: trial of 90 days<br>
        Expiration: {expired_at}

            <br>Accelerate Playbook creation with AI-driven content recommendations
            from <b>IBM Watsonx Code Assistant for Red Hat Ansible Lightspeed</b>,
            enabling faster, more efficient automation development. <a href=
            "https://www.ibm.com/products/watsonx-code-assistant-ansible-lightspeed">
            Learn more</a>.
        """
        self.assertEqual(dedent(expectation).strip(), content)

        user.delete()
        trial_plan.delete()

    @override_settings(ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL=True)
    @override_settings(AUTHZ_DUMMY_ORGS_WITH_SUBSCRIPTION="*")
    def test_get_view_expired_trial(self):
        user = create_user_with_provider(provider=USER_SOCIAL_AUTH_PROVIDER_OIDC)
        self.client.force_login(user=user)

        trial_plan, _ = Plan.objects.get_or_create(name=TRIAL_PLAN_NAME, expires_after="90 days")
        user.plans.add(trial_plan)
        up = user.userplan_set.first()
        up.expired_at = datetime.now(timezone.utc) + timedelta(days=-1)
        up.save()
        user.userplan_set.first().expired_at = ""

        r = self.client.get(self.api_version_reverse("me_summary"))
        self.assertEqual(r.status_code, 200)
        content = r.json()["content"]
        self.assertTrue(
            "Your trial has expired. To continue your Ansible automation journey" in content
        )

        user.delete()
        trial_plan.delete()


@override_settings(CHATBOT_DEFAULT_PROVIDER="wisdom")
@override_settings(ANSIBLE_AI_CHATBOT_NAME="Awesome Chatbot")
@override_settings(CHATBOT_DEBUG_UI=False)
@override_settings(AUTHZ_DUMMY_ORGS_WITH_SUBSCRIPTION="12345")
class TestChatbotView(TestCase):
    CHATBOT_PAGE_TITLE = "<title>Awesome Chatbot</title>"
    DOCUMENT_URL = (
        'href="https://access.redhat.com/documentation/en-us/'
        'red_hat_ansible_lightspeed_with_ibm_watsonx_code_assistant/2.x_latest"'
    )

    def setUp(self):
        super().setUp()
        self.non_rh_user = get_user_model().objects.create_user(
            username="non-rh-user",
            password="non-rh-password",
            email="non-rh-user@email.com",
            rh_internal=False,
        )
        self.rh_user = get_user_model().objects.create_user(
            username="rh-user",
            password="rh-password",
            email="rh-user@redhat.com",
            rh_internal=True,
        )
        self.test_group = Group(name="test")
        self.test_group.save()
        self.non_rh_test_user = get_user_model().objects.create_user(
            username="non-rh-test-user",
            password="non-rh-test-password",
            email="non-rh-test-user@email.com",
            rh_internal=False,
        )
        self.non_rh_test_user.groups.add(self.test_group)
        self.non_rh_user_with_subscription = create_user_with_provider(
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            username="non-rh-user-with-subscription",
            password="non-rh-password",
            email="non-rh-user-with-subscription@email.com",
            rh_internal=False,
            rh_org_id=12345,
        )

    def tearDown(self):
        self.non_rh_user.delete()
        self.rh_user.delete()
        self.non_rh_test_user.delete()
        self.test_group.delete()
        self.non_rh_user_with_subscription.delete()
        Organization.objects.filter(id=12345).delete()

    def test_chatbot_view_with_anonymous_user(self):
        r = self.client.get(reverse("chatbot"))
        self.assertEqual(r.status_code, HTTPStatus.FOUND)
        self.assertEqual(r.url, "/login?next=/chatbot/")

    def test_chatbot_view_with_non_rh_user(self):
        self.client.force_login(user=self.non_rh_user)
        r = self.client.get(reverse("chatbot"))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)

    def test_chatbot_view_with_non_rh_user_and_subscription(self):
        self.client.force_login(user=self.non_rh_user_with_subscription)
        r = self.client.get(reverse("chatbot"))
        self.assertEqual(r.status_code, HTTPStatus.OK)

    @override_settings(CHATBOT_DEFAULT_PROVIDER="")
    def test_chatbot_view_with_rh_user_but_chatbot_disabled(self):
        self.client.force_login(user=self.rh_user)
        r = self.client.get(reverse("chatbot"))
        self.assertEqual(r.status_code, HTTPStatus.FOUND)
        self.assertEqual(r.url, "/")

    def test_chatbot_view_with_rh_user(self):
        self.client.force_login(user=self.rh_user)
        r = self.client.get(reverse("chatbot"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertContains(r, TestChatbotView.CHATBOT_PAGE_TITLE)
        self.assertContains(r, self.rh_user.username)
        self.assertContains(r, '<div id="debug" hidden>false</div>')
        self.assertContains(r, '<div id="stream" hidden>true</div>')

    @override_settings(CHATBOT_DEBUG_UI=True)
    def test_chatbot_view_with_debug_ui(self):
        self.client.force_login(user=self.rh_user)
        r = self.client.get(reverse("chatbot"), {"debug": "true"})
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertContains(r, '<div id="debug" hidden>true</div>')

    @patch("ansible_ai_connect.main.views.ChatbotView.getModelPipelineChatBot")
    @patch("ansible_ai_connect.main.views.ChatbotView.getModelStreamingPipelineChatBot")
    def test_chatbot_view_with_chatbot_disabled(self, mock1, mock2):
        mock1.return_value = NopStreamingChatBotPipeline(NopConfiguration())
        mock2.return_value = NopChatBotPipeline(NopConfiguration())
        self.client.force_login(user=self.rh_user)
        r = self.client.get(reverse("chatbot"), {"stream": "true"})
        # Chatbot is disabled and return 302 to redirect to home
        self.assertEqual(r.status_code, HTTPStatus.FOUND)

    @patch("ansible_ai_connect.main.views.ChatbotView.getModelStreamingPipelineChatBot")
    def test_chatbot_view_with_streaming_disabled(self, mock1):
        mock1.return_value = NopStreamingChatBotPipeline(NopConfiguration())
        self.client.force_login(user=self.rh_user)
        r = self.client.get(reverse("chatbot"), {"stream": "true"})
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertContains(r, '<div id="stream" hidden>false</div>')

    @patch("ansible_ai_connect.main.views.ChatbotView.getModelPipelineChatBot")
    def test_chatbot_view_with_non_streaming_disabled(self, mock1):
        mock1.return_value = NopChatBotPipeline(NopConfiguration())
        self.client.force_login(user=self.rh_user)
        r = self.client.get(reverse("chatbot"), {"stream": "true"})
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertContains(r, '<div id="stream" hidden>true</div>')
