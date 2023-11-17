#!/usr/bin/env python3
from http import HTTPStatus
from unittest.mock import Mock, patch

import boto3
import users.models
from ai.api.aws.wca_secret_manager import WcaSecretManager
from ai.api.tests.test_views import APITransactionTestCase
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from users.constants import (
    USER_SOCIAL_AUTH_PROVIDER_GITHUB,
    USER_SOCIAL_AUTH_PROVIDER_OIDC,
)
from users.tests.test_users import create_user


def no_secret(*args, **kwargs):
    return ""


def with_secret(*args, **kwargs):
    return "my-secret"


def bypass_init(*args, **kwargs):
    return None


@patch.object(WcaSecretManager, "__init__", bypass_init)
@patch.object(boto3, "client", Mock())
class UserHomeTestAsAnonymous(TestCase):
    def setUp(self):
        self.client = Client()

    def test_unauthorized(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please log in using the button below.")
        self.assertNotContains(response, "Role:")
        self.assertNotContains(response, "pf-c-alert__title")
        self.assertNotContains(response, "Admin Portal")


@patch.object(WcaSecretManager, "__init__", bypass_init)
@patch.object(boto3, "client", Mock())
class UserHomeTestAsAdmin(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = create_user(provider="oidc", rh_user_is_org_admin=True)
        self.client.force_login(self.user)

    def tearDown(self):
        self.user.delete()

    @patch.object(WcaSecretManager, "get_secret", no_secret)
    @patch.object(users.models.User, "rh_org_has_subscription", True)
    @patch.object(users.models.User, "rh_user_has_seat", True)
    def test_rh_admin_with_seat_and_no_secret(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Role: administrator, licensed user")
        self.assertContains(response, "pf-c-alert__title")
        self.assertContains(response, "model settings have not been configured")
        self.assertContains(response, "Admin Portal")

    @patch.object(WcaSecretManager, "get_secret", with_secret)
    @patch.object(users.models.User, "rh_org_has_subscription", False)
    @patch.object(users.models.User, "rh_user_has_seat", False)
    def test_rh_admin_without_seat_and_with_secret(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Role:")
        self.assertNotContains(response, "pf-c-alert__title")
        self.assertNotContains(response, "Admin Portal")

    @patch.object(WcaSecretManager, "get_secret", with_secret)
    @patch.object(users.models.User, "rh_org_has_subscription", True)
    @patch.object(users.models.User, "rh_user_has_seat", True)
    def test_rh_admin_with_a_seat_and_with_secret(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Role: administrator, licensed user")
        self.assertNotContains(response, "pf-c-alert__title")
        self.assertContains(response, "Admin Portal")


@patch.object(WcaSecretManager, "__init__", bypass_init)
@patch.object(boto3, "client", Mock())
class UserHomeTestAsUser(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = create_user(provider="oidc", rh_user_is_org_admin=False)
        self.client.force_login(self.user)

    def tearDown(self):
        self.user.delete()

    @patch.object(WcaSecretManager, "get_secret", with_secret)
    @patch.object(users.models.User, "rh_org_has_subscription", True)
    @patch.object(users.models.User, "rh_user_has_seat", False)
    def test_rh_user_without_seat_and_no_secret(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Role:")
        self.assertContains(response, "pf-c-alert__title")
        self.assertContains(response, "You do not have a licensed seat for Ansible Lightspeed")
        self.assertNotContains(response, "Admin Portal")

    @patch.object(WcaSecretManager, "get_secret", no_secret)
    @patch.object(users.models.User, "rh_org_has_subscription", True)
    @patch.object(users.models.User, "rh_user_has_seat", True)
    def test_rh_user_with_a_seat_and_no_secret(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Role: licensed user")
        self.assertContains(response, "but your administrator has not configured the service")
        self.assertNotContains(response, "Admin Portal")

    @patch.object(WcaSecretManager, "get_secret", with_secret)
    @patch.object(users.models.User, "rh_org_has_subscription", True)
    @patch.object(users.models.User, "rh_user_has_seat", True)
    def test_rh_user_with_a_seat_and_with_secret(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Role: licensed user")
        self.assertContains(
            response, "Red Hat Ansible Lightspeed with IBM watsonx Code Assistant</h1>"
        )
        self.assertNotContains(response, "pf-c-alert__title")
        self.assertNotContains(response, "Admin Portal")


class TestHomeDocumentationUrl(APITransactionTestCase):
    def setUp(self) -> None:
        self.password = "somepassword"

    @override_settings(COMMERCIAL_DOCUMENTATION_URL="https://official_docs")
    @patch.object(users.models.User, "rh_user_has_seat", True)
    def test_docs_url_for_seated_user(self):
        self.user = create_user(
            password=self.password,
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
        )
        self.client.login(username=self.user.username, password=self.password)
        r = self.client.get(reverse('home'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertIn("https://official_docs", str(r.content))

    @override_settings(DOCUMENTATION_URL="https://community_docs")
    @patch.object(users.models.User, "rh_user_has_seat", False)
    def test_docs_url_for_unseated_user(self):
        self.user = create_user(
            password=self.password,
            provider=USER_SOCIAL_AUTH_PROVIDER_GITHUB,
        )
        self.client.login(username=self.user.username, password=self.password)
        r = self.client.get(reverse('home'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertIn("https://community_docs", str(r.content))

    @override_settings(DOCUMENTATION_URL="https://community_docs")
    def test_docs_url_for_not_logged_in_user(self):
        r = self.client.get(reverse('home'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertIn("https://community_docs", str(r.content))
