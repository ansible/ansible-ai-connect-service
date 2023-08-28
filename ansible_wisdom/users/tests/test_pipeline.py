#!/usr/bin/env python3


from uuid import uuid4

from django.contrib.auth import get_user_model
from social_django.models import UserSocialAuth
from test_utils import WisdomServiceLogAwareTestCase
from users.pipeline import load_extra_data


class TestExtraData(WisdomServiceLogAwareTestCase):
    def setUp(self):
        self.sso_user = get_user_model().objects.create_user(
            username="sso-user",
            email="sso@user.nowhere",
            password="bar",
        )
        self.usa = UserSocialAuth.objects.create(
            user=self.sso_user, provider="oidc", uid=str(uuid4())
        )

    def tearDown(self):
        self.sso_user.delete()

    def test_load_extra_data(self):
        class DummyBackend:
            def extra_data(*args, **kwargs):
                return {
                    "id": "1231243",
                    "login": "my-login",
                    "id_token": "some-string",
                    "token_type": "Bearer",
                }

        load_extra_data(
            backend=DummyBackend(),
            details=None,
            response=None,
            uid=None,
            user=self.sso_user,
            social=self.usa,
        )
        assert self.usa.extra_data == {"login": "my-login"}
