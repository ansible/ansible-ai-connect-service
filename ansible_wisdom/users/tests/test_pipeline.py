#!/usr/bin/env python3


from uuid import uuid4

import jwt
from django.contrib.auth import get_user_model
from django.test import override_settings
from social_django.models import UserSocialAuth
from test_utils import WisdomServiceLogAwareTestCase
from users.pipeline import load_extra_data, redhat_organization


def build_access_token(payload):
    return jwt.encode(payload, key='secret', algorithm='HS256')


class DummyGithubBackend:
    id_token = {}
    name = "github"

    def extra_data(*args, **kwargs):
        return {
            "id": "1231243",
            "login": "my-login",
            "id_token": "some-string",
            "token_type": "Bearer",
        }


class DummyRHBackend:
    id_token = {"organization": {"id": 345}}
    name = "oidc"

    def extra_data(*args, **kwargs):
        return {
            "id": "1231243",
            "login": "my-login",
            "id_token": "some-string",
            "token_type": "Bearer",
        }


@override_settings(AUTHZ_BACKEND_TYPE="dummy")
class TestExtraData(WisdomServiceLogAwareTestCase):
    def setUp(self):
        self.rh_user = get_user_model().objects.create_user(
            username="rh-user",
            email="sso@user.nowhere",
            password="bar",
        )
        self.rh_usa = UserSocialAuth.objects.create(
            user=self.rh_user, provider="oidc", uid=str(uuid4())
        )

        self.github_user = get_user_model().objects.create_user(
            username="github-user",
            email="sso@user.nowhere",
            password="bar",
        )
        self.github_usa = UserSocialAuth.objects.create(
            user=self.rh_user, provider="github", uid=str(uuid4())
        )

    def tearDown(self):
        self.rh_user.delete()
        self.github_user.delete()

    def test_load_extra_data(self):
        load_extra_data(
            backend=DummyRHBackend(),
            details=None,
            response=None,
            uid=None,
            user=self.rh_user,
            social=self.rh_usa,
        )
        self.assertEqual(self.rh_user.external_username, "my-login")

    def test_redhat_organization_with_rh_admin_user(self):
        response = {
            "access_token": build_access_token(
                {"realm_access": {"roles": ["admin:org:all"]}, "preferred_username": "jean-michel"}
            )
        }

        answer = redhat_organization(backend=DummyRHBackend(), user=self.rh_user, response=response)
        assert answer == {
            'organization_id': 345,
            'rh_user_is_org_admin': True,
            'external_username': "jean-michel",
        }
        assert self.rh_user.organization.id == 345
        assert self.rh_user.rh_user_is_org_admin is True
        assert self.rh_user.external_username == "jean-michel"

    def test_redhat_organization_with_rh_user(self):
        response = {
            "access_token": build_access_token(
                {"realm_access": {"roles": ["another_other_role"]}, "preferred_username": "yves"}
            )
        }

        answer = redhat_organization(backend=DummyRHBackend(), user=self.rh_user, response=response)
        assert answer == {
            'organization_id': 345,
            'rh_user_is_org_admin': False,
            'external_username': "yves",
        }
        assert self.rh_user.organization.id == 345
        assert self.rh_user.rh_user_is_org_admin is False
        assert self.rh_user.external_username == "yves"

    def test_redhat_organization_with_github_user(self):
        response = {"access_token": build_access_token({})}

        answer = redhat_organization(
            backend=DummyGithubBackend(), user=self.github_user, response=response
        )
        assert answer is None
        assert self.rh_user.organization is None
        assert self.rh_user.rh_user_is_org_admin is False

    @override_settings(AUTHZ_DUMMY_RH_ORG_ADMINS="yves")
    def test_redhat_organization_with_AUTHZ_DUMMY_parameter(self):
        response = {
            "access_token": build_access_token(
                {"realm_access": {"roles": ["another_other_role"]}, "preferred_username": "yves"}
            )
        }

        answer = redhat_organization(backend=DummyRHBackend(), user=self.rh_user, response=response)
        assert answer == {
            'organization_id': 345,
            'rh_user_is_org_admin': True,
            'external_username': "yves",
        }
        assert self.rh_user.organization.id == 345
        assert self.rh_user.rh_user_is_org_admin is True
        assert self.rh_user.external_username == "yves"

    @override_settings(AUTHZ_DUMMY_RH_ORG_ADMINS="*")
    def test_redhat_organization_with_AUTHZ_DUMMY_wildcard(self):
        response = {
            "access_token": build_access_token(
                {"realm_access": {"roles": ["another_other_role"]}, "preferred_username": "yves"}
            )
        }

        answer = redhat_organization(backend=DummyRHBackend(), user=self.rh_user, response=response)
        assert answer == {
            'organization_id': 345,
            'rh_user_is_org_admin': True,
            'external_username': "yves",
        }
        assert self.rh_user.organization.id == 345
        assert self.rh_user.rh_user_is_org_admin is True
        assert self.rh_user.external_username == "yves"

    @override_settings(AUTHZ_DUMMY_RH_ORG_ADMINS=1)
    def test_redhat_organization_with_invalid_AUTHZ_DUMMY_parameter(self):
        response = {
            "access_token": build_access_token(
                {"realm_access": {"roles": ["another_other_role"]}, "preferred_username": "yves"}
            )
        }
        with self.assertLogs(logger='users.pipeline', level='ERROR') as log:
            answer = redhat_organization(
                backend=DummyRHBackend(), user=self.rh_user, response=response
            )
            self.assertInLog("AUTHZ_DUMMY_RH_ORG_ADMINS has an invalid format.", log)

        assert answer == {
            'organization_id': 345,
            'rh_user_is_org_admin': False,
            'external_username': "yves",
        }
        assert self.rh_user.organization.id == 345
        assert self.rh_user.rh_user_is_org_admin is False
        assert self.rh_user.external_username == "yves"
