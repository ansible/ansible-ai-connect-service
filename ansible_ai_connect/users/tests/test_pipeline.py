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

from uuid import uuid4

import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from django.contrib.auth import get_user_model
from django.test import override_settings
from social_django.models import UserSocialAuth

from ansible_ai_connect.test_utils import WisdomServiceLogAwareTestCase
from ansible_ai_connect.users.constants import RHSSO_LIGHTSPEED_SCOPE
from ansible_ai_connect.users.pipeline import load_extra_data, redhat_organization


def build_access_token(private_key, payload):
    payload["aud"] = [RHSSO_LIGHTSPEED_SCOPE]
    return jwt.encode(payload, key=private_key, algorithm="RS256")


class DummyGithubBackend:
    name = "github"

    def extra_data(*args, **kwargs):
        return {
            "id": "1231243",
            "login": "my-login",
            "id_token": "some-string",
            "token_type": "Bearer",
        }


class DummyRHBackend:
    name = "oidc"

    def __init__(self, public_key):
        self.public_key = public_key

    def find_valid_key(self, id_token):
        return self.public_key

    def extra_data(*args, **kwargs):
        return {
            "id": "1231243",
            "login": "my-login",
            "id_token": "some-string",
            "token_type": "Bearer",
        }


class DummyAAPBackend:
    name = "aap"

    def __init__(self, public_key):
        self.public_key = public_key

    def find_valid_key(self, id_token):
        return self.public_key

    def extra_data(*args, **kwargs):
        return {
            "id": "1231243",
            "login": "my-login",
            "id_token": "some-string",
            "token_type": "Bearer",
            "aap_licensed": True,
            "aap_system_auditor": True,
            "aap_superuser": True,
        }


@override_settings(SEGMENT_WRITE_KEY=None)
@override_settings(AUTHZ_BACKEND_TYPE="dummy")
class TestExtraData(WisdomServiceLogAwareTestCase):
    def setUp(self):
        super().setUp()
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
            email="gh@user.nowhere",
            password="bar",
        )
        self.github_usa = UserSocialAuth.objects.create(
            user=self.github_user, provider="github", uid=str(uuid4())
        )
        self.aap_user = get_user_model().objects.create_user(
            username="aap-user",
            email="aap@user.nowhere",
            password="bar",
        )
        self.aap_usa = UserSocialAuth.objects.create(
            user=self.aap_user, provider="aap", uid=str(uuid4())
        )
        self.rsa_private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
        )
        algo = jwt.algorithms.RSAAlgorithm(jwt.algorithms.RSAAlgorithm.SHA256)
        self.jwk_public_key = algo.to_jwk(self.rsa_private_key.public_key(), as_dict=True)
        self.jwk_public_key["alg"] = "RS256"

    def tearDown(self):
        self.rh_user.delete()
        self.github_user.delete()
        self.aap_user.delete()
        super().tearDown()

    def test_load_extra_data(self):
        load_extra_data(
            backend=DummyRHBackend(public_key=self.jwk_public_key),
            details=None,
            response=None,
            uid=None,
            user=self.rh_user,
            social=self.rh_usa,
        )
        self.assertEqual(self.rh_user.external_username, "my-login")
        self.assertFalse(self.rh_user.rh_aap_licensed)
        self.assertFalse(self.rh_user.rh_aap_system_auditor)
        self.assertFalse(self.rh_user.rh_aap_superuser)

    def test_load_extra_data_aap(self):
        load_extra_data(
            backend=DummyAAPBackend(public_key=self.jwk_public_key),
            details=None,
            response=None,
            uid=None,
            user=self.aap_user,
            social=self.aap_usa,
        )
        self.assertEqual(self.aap_user.external_username, "my-login")
        self.assertTrue(self.aap_user.rh_aap_licensed)
        self.assertTrue(self.aap_user.rh_aap_system_auditor)
        self.assertTrue(self.aap_user.rh_aap_superuser)

    def test_redhat_organization_with_rh_admin_user(self):
        response = {
            "access_token": build_access_token(
                self.rsa_private_key,
                {
                    "realm_access": {"roles": ["admin:org:all"]},
                    "preferred_username": "jean-michel",
                    "organization": {"id": "345"},
                },
            )
        }

        answer = redhat_organization(
            backend=DummyRHBackend(public_key=self.jwk_public_key),
            user=self.rh_user,
            response=response,
        )
        assert answer == {
            "organization_id": 345,
            "rh_employee": False,
            "rh_user_is_org_admin": True,
            "external_username": "jean-michel",
        }
        assert self.rh_user.organization.id == 345
        assert self.rh_user.rh_user_is_org_admin is True
        assert self.rh_user.external_username == "jean-michel"

    def test_redhat_organization_with_rh_user(self):
        response = {
            "access_token": build_access_token(
                self.rsa_private_key,
                {
                    "realm_access": {"roles": ["another_other_role"]},
                    "preferred_username": "yves",
                    "organization": {"id": "345"},
                },
            )
        }

        answer = redhat_organization(
            backend=DummyRHBackend(public_key=self.jwk_public_key),
            user=self.rh_user,
            response=response,
        )
        assert answer == {
            "organization_id": 345,
            "rh_employee": False,
            "rh_user_is_org_admin": False,
            "external_username": "yves",
        }
        assert self.rh_user.organization.id == 345
        assert self.rh_user.rh_user_is_org_admin is False
        assert self.rh_user.external_username == "yves"

    def test_redhat_organization_with_github_user(self):
        response = {"access_token": build_access_token(self.rsa_private_key, {})}

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
                self.rsa_private_key,
                {
                    "realm_access": {"roles": ["another_other_role"]},
                    "preferred_username": "yves",
                    "organization": {"id": "345"},
                },
            )
        }

        answer = redhat_organization(
            backend=DummyRHBackend(public_key=self.jwk_public_key),
            user=self.rh_user,
            response=response,
        )
        assert answer == {
            "organization_id": 345,
            "rh_employee": False,
            "rh_user_is_org_admin": True,
            "external_username": "yves",
        }
        assert self.rh_user.organization.id == 345
        assert self.rh_user.rh_user_is_org_admin is True
        assert self.rh_user.external_username == "yves"

    @override_settings(AUTHZ_DUMMY_RH_ORG_ADMINS="*")
    def test_redhat_organization_with_AUTHZ_DUMMY_wildcard(self):
        response = {
            "access_token": build_access_token(
                self.rsa_private_key,
                {
                    "realm_access": {"roles": ["another_other_role"]},
                    "preferred_username": "yves",
                    "organization": {"id": "345"},
                },
            )
        }

        answer = redhat_organization(
            backend=DummyRHBackend(public_key=self.jwk_public_key),
            user=self.rh_user,
            response=response,
        )
        assert answer == {
            "organization_id": 345,
            "rh_employee": False,
            "rh_user_is_org_admin": True,
            "external_username": "yves",
        }
        assert self.rh_user.organization.id == 345
        assert self.rh_user.rh_user_is_org_admin is True
        assert self.rh_user.external_username == "yves"

    @override_settings(AUTHZ_DUMMY_RH_ORG_ADMINS=1)
    def test_redhat_organization_with_invalid_AUTHZ_DUMMY_parameter(self):
        response = {
            "access_token": build_access_token(
                self.rsa_private_key,
                {
                    "realm_access": {"roles": ["another_other_role"]},
                    "preferred_username": "yves",
                    "organization": {"id": "345"},
                },
            )
        }
        with self.assertLogs(logger="ansible_ai_connect.users.pipeline", level="ERROR") as log:
            answer = redhat_organization(
                backend=DummyRHBackend(public_key=self.jwk_public_key),
                user=self.rh_user,
                response=response,
            )
            self.assertInLog("AUTHZ_DUMMY_RH_ORG_ADMINS has an invalid format.", log)

        assert answer == {
            "organization_id": 345,
            "rh_employee": False,
            "rh_user_is_org_admin": False,
            "external_username": "yves",
        }
        assert self.rh_user.organization.id == 345
        assert self.rh_user.rh_user_is_org_admin is False
        assert self.rh_user.external_username == "yves"

    def test_rh_employee_field(self):
        response = {
            "access_token": build_access_token(
                self.rsa_private_key,
                {
                    "realm_access": {"roles": ["redhat:employees"]},
                    "preferred_username": "jean-michel",
                    "organization": {"id": "345"},
                },
            )
        }

        answer = redhat_organization(
            backend=DummyRHBackend(public_key=self.jwk_public_key),
            user=self.rh_user,
            response=response,
        )
        self.assertEqual(answer["rh_employee"], True)

    def test_rhoss_user_and_email(self):
        response = {
            "access_token": build_access_token(
                self.rsa_private_key,
                {
                    "family_name": "Drake",
                    "email": "francis.drake@example.foo",
                    "given_name": "Francis",
                    "name": "Francis Drake",
                    "organization": {"id": "345"},
                    "preferred_username": "fdrake01",
                },
            )
        }

        redhat_organization(
            backend=DummyRHBackend(public_key=self.jwk_public_key),
            user=self.rh_user,
            response=response,
        )
        self.assertEqual(self.rh_user.family_name, "Drake")
        self.assertEqual(self.rh_user.email, "francis.drake@example.foo")
        self.assertEqual(self.rh_user.given_name, "Francis")
        self.assertEqual(self.rh_user.name, "Francis Drake")
