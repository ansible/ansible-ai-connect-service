#!/usr/bin/env python3

from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponseRedirect
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from ansible_wisdom.main.settings.base import SOCIAL_AUTH_OIDC_KEY
from ansible_wisdom.main.views import LoginView
from ansible_wisdom.users.constants import (
    USER_SOCIAL_AUTH_PROVIDER_AAP,
    USER_SOCIAL_AUTH_PROVIDER_GITHUB,
    USER_SOCIAL_AUTH_PROVIDER_OIDC,
)
from ansible_wisdom.users.tests.test_users import create_user


def create_user_with_provider(user_provider):
    return create_user(
        username='test_user_name',
        password='test_passwords',
        provider=user_provider,
        external_username='anexternalusername',
    )


class LogoutTest(TestCase):
    def test_rht_sso_redirect(self):
        user = create_user_with_provider(USER_SOCIAL_AUTH_PROVIDER_OIDC)
        self.client.force_login(user)

        response = self.client.get(reverse('logout'))
        self.assertEqual(
            response.url,
            'https://sso.redhat.com/auth/realms/redhat-external/protocol/openid'
            '-connect/logout?post_logout_redirect_uri=http://testserver/'
            f'&client_id={SOCIAL_AUTH_OIDC_KEY}',
        )

    def test_gh_sso_redirect(self):
        user = create_user_with_provider(USER_SOCIAL_AUTH_PROVIDER_GITHUB)
        self.client.force_login(user)

        response = self.client.get(reverse('logout'))
        self.assertEqual(response.url, '/')

    @override_settings(AAP_API_URL='http://aap/api')
    def test_aap_sso_redirect(self):
        user = create_user_with_provider(USER_SOCIAL_AUTH_PROVIDER_AAP)
        self.client.force_login(user)

        response = self.client.get(reverse('logout'))
        self.assertEqual(response.url, 'http://aap/api/logout/?next=http://testserver/')


class AlreadyAuth(TestCase):
    def test_login(self):
        request = RequestFactory().get("/login")
        request.user = AnonymousUser()
        response = LoginView.as_view()(request)
        response.render()
        contents = response.content.decode()
        self.assertIn("You are currently not logged in.", contents)
        self.assertIn("Log in with Red Hat", contents)

    @override_settings(DEPLOYMENT_MODE='onprem')
    def test_login_aap(self):
        request = RequestFactory().get("/login")
        request.user = AnonymousUser()
        response = LoginView.as_view()(request)
        response.render()
        contents = response.content.decode()
        self.assertIn("You are currently not logged in.", contents)
        self.assertIn("Log in with AAP", contents)

    @override_settings(DEPLOYMENT_MODE='upstream')
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
