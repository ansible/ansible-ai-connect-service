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
from unittest.mock import Mock, patch

import boto3
from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.urls import reverse

import ansible_ai_connect.users.models
from ansible_ai_connect.ai.api.tests.test_views import APITransactionTestCase
from ansible_ai_connect.test_utils import WisdomAppsBackendMocking
from ansible_ai_connect.users.constants import (
    USER_SOCIAL_AUTH_PROVIDER_GITHUB,
    USER_SOCIAL_AUTH_PROVIDER_OIDC,
)
from ansible_ai_connect.users.tests.test_users import create_user


def bypass_init(*args, **kwargs):
    return None


@override_settings(WCA_SECRET_BACKEND_TYPE='dummy')
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
        self.assertContains(response, "pf-c-alert__title", count=1)
        self.assertNotContains(response, "Admin Portal")

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    def test_unauthorized_with_tech_preview(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, "Log in to Tech Preview")

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=False)
    def test_unauthorized_without_tech_preview(self):
        response = self.client.get(reverse("login"))
        self.assertNotContains(response, "Log in to Tech Preview")


@override_settings(WCA_SECRET_BACKEND_TYPE='dummy')
@override_settings(WCA_SECRET_DUMMY_SECRETS='')
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
        self.assertContains(response, "pf-c-alert__title", count=2)
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
        self.assertContains(response, "pf-c-alert__title")
        self.assertContains(response, "Your organization doesn't have access to Project Name.")
        self.assertContains(
            response,
            "You do not have an Active subscription to Ansible Automation Platform "
            "which is required to use Project Name.",
        )
        self.assertContains(response, "The Project Name Technical Preview is no longer available")
        self.assertContains(response, "Role: administrator")
        self.assertContains(response, "Admin Portal")

    @override_settings(WCA_SECRET_DUMMY_SECRETS='1234567:valid')
    @patch.object(ansible_ai_connect.users.models.User, "rh_org_has_subscription", True)
    @patch.object(ansible_ai_connect.users.models.User, "rh_user_has_seat", True)
    def test_rh_admin_with_a_seat_and_with_secret(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Role: administrator, licensed user")
        self.assertContains(response, "pf-c-alert__title", count=1)
        self.assertContains(response, "Admin Portal")


@override_settings(WCA_SECRET_BACKEND_TYPE='dummy')
@override_settings(WCA_SECRET_DUMMY_SECRETS='')
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
    @override_settings(WCA_SECRET_DUMMY_SECRETS='')
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
    @override_settings(WCA_SECRET_DUMMY_SECRETS='valid')
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
    @override_settings(WCA_SECRET_DUMMY_SECRETS='')
    @patch.object(ansible_ai_connect.users.models.User, "rh_org_has_subscription", True)
    @patch.object(ansible_ai_connect.users.models.User, "rh_user_has_seat", False)
    def test_rh_user_without_seat_and_no_secret_without_tech_preview(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Role:")
        self.assertContains(response, "pf-c-alert__title", count=1)
        self.assertContains(response, "You do not have a licensed seat for Project Name")
        self.assertNotContains(response, "You will be limited to features of the Project Name")
        self.assertNotContains(response, "Admin Portal")
        self.assertContains(response, "The Project Name Technical Preview is no longer available")

    @override_settings(WCA_SECRET_DUMMY_SECRETS='')
    @patch.object(ansible_ai_connect.users.models.User, "rh_org_has_subscription", True)
    @patch.object(ansible_ai_connect.users.models.User, "rh_user_has_seat", True)
    def test_rh_user_with_a_seat_and_no_secret(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Role: licensed user")
        self.assertContains(response, "but your administrator has not configured the service")
        self.assertNotContains(response, "Admin Portal")

    @override_settings(WCA_SECRET_DUMMY_SECRETS='1234567:valid')
    @override_settings(ANSIBLE_AI_PROJECT_NAME="Project Name")
    @patch.object(ansible_ai_connect.users.models.User, "rh_org_has_subscription", True)
    @patch.object(ansible_ai_connect.users.models.User, "rh_user_has_seat", True)
    def test_rh_user_with_a_seat_and_with_secret(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Role: licensed user")
        self.assertContains(response, "Project Name</h1>")
        self.assertContains(response, "pf-c-alert__title", count=1)
        self.assertNotContains(response, "Admin Portal")

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    @override_settings(WCA_SECRET_DUMMY_SECRETS='1234567:valid')
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
        self.assertContains(response, "The Project Name Technical Preview is no longer available")


@override_settings(AUTHZ_BACKEND_TYPE='dummy')
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
        r = self.client.get(reverse('home'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertIn("https://official_docs", str(r.content))

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    @override_settings(DOCUMENTATION_URL="https://community_docs")
    @patch.object(ansible_ai_connect.users.models.User, "rh_user_has_seat", False)
    def test_docs_url_for_unseated_user_with_tech_preview(self):
        self.user = create_user(
            password=self.password,
            provider=USER_SOCIAL_AUTH_PROVIDER_GITHUB,
        )
        self.client.login(username=self.user.username, password=self.password)
        r = self.client.get(reverse('home'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertContains(r, "pf-c-alert__title", count=1)
        self.assertIn("https://community_docs", str(r.content))

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=False)
    @override_settings(ANSIBLE_AI_PROJECT_NAME="Project Name")
    @patch.object(ansible_ai_connect.users.models.User, "rh_user_has_seat", False)
    def test_docs_url_for_unseated_user_without_tech_preview(self):
        self.user = create_user(
            password=self.password,
            provider=USER_SOCIAL_AUTH_PROVIDER_GITHUB,
        )
        self.client.login(username=self.user.username, password=self.password)
        r = self.client.get(reverse('home'))
        self.assertContains(r, "pf-c-alert__title", count=1)
        self.assertContains(r, "Your organization doesn't have access to Project Name.")
        self.assertIn(settings.COMMERCIAL_DOCUMENTATION_URL, str(r.content))

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    @override_settings(DOCUMENTATION_URL="https://community_docs")
    def test_docs_url_for_not_logged_in_user_with_tech_preview(self):
        r = self.client.get(reverse('home'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertIn("https://community_docs", str(r.content))

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=False)
    def test_docs_url_for_not_logged_in_user_without_tech_preview(self):
        r = self.client.get(reverse('home'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertIn(settings.COMMERCIAL_DOCUMENTATION_URL, str(r.content))
