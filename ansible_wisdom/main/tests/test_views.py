#!/usr/bin/env python3

from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponseRedirect
from django.test import RequestFactory, TestCase
from main.views import LoginView, LogoutView


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
    user = UserMock()
    view = LogoutView()

    def test_rht_sso_redirect(self):
        self.user.is_oidc = True
        self.request.user = self.user

        self.assertEqual(
            self.view.get_next_page(self.request),
            'https://sso.redhat.com/auth/realms/redhat-external/protocol/openid'
            '-connect/logout?redirect_uri=http://localhost/',
        )

    def test_gh_sso_redirect(self):
        self.user.is_oidc = False
        self.request.user = self.user

        self.assertEqual(self.view.get_next_page(self.request), None)


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
