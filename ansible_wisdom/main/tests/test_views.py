#!/usr/bin/env python3

from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponseRedirect
from django.test import RequestFactory, TestCase
from django.urls import reverse
from main.settings.base import SOCIAL_AUTH_OIDC_KEY
from main.views import LoginView, LogoutView
from users.constants import (
    USER_SOCIAL_AUTH_PROVIDER_GITHUB,
    USER_SOCIAL_AUTH_PROVIDER_OIDC,
)
from users.tests.test_users import create_user


class RequestMock:
    user = None
    host = "http://localhost"

    def build_absolute_uri(self, path):
        return self.host + path


class UserMock:
    is_oidc = False

    def is_oidc_user(self):
        return self.is_oidc


class LogoutTest(TestCase):
    request = RequestMock()
    user = None
    view = LogoutView()

    def test_rht_sso_redirect(self):
        self.user = create_user(
            username='test_user_name',
            password='test_passwords',
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            external_username='anexternalusername',
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('logout'))
        self.assertEqual(
            response.url,
            'https://sso.redhat.com/auth/realms/redhat-external/protocol/openid'
            '-connect/logout?post_logout_redirect_uri=http://testserver/'
            f'&client_id={SOCIAL_AUTH_OIDC_KEY}',
        )

    def test_gh_sso_redirect(self):
        self.user = create_user(
            username='test_user_name',
            password='test_passwords',
            provider=USER_SOCIAL_AUTH_PROVIDER_GITHUB,
            external_username='anexternalusername',
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('logout'))
        self.assertEqual(response.url, '/')


class AlreadyAuth(TestCase):
    def test_login(self):
        request = RequestFactory().get("/login")
        request.user = AnonymousUser()
        response = LoginView.as_view()(request)
        response.render()
        self.assertIn("You are currently not logged in.", response.content.decode())

    def test_no_login_for_auth_user(self):
        class MockUser:
            is_authenticated = True

        request = RequestFactory().get("/login")
        request.user = MockUser()
        response = LoginView.as_view()(request)
        self.assertTrue(isinstance(response, HttpResponseRedirect))
        self.assertEqual(response.url, "/")
