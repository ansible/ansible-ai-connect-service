#!/usr/bin/env python3

from unittest.mock import Mock
from uuid import uuid4

from django.contrib.auth import get_user_model
from social_django.models import UserSocialAuth

from ansible_wisdom.test_utils import WisdomServiceLogAwareTestCase
from ansible_wisdom.users.management.commands.fix_users_with_two_sso_providers import (
    Command,
)


class TestFixUsersWithTwoSSOProviders(WisdomServiceLogAwareTestCase):
    def setUp(self):
        self.sso_user = get_user_model().objects.create_user(
            username="sso-user",
            email="sso@user.nowhere",
            password="bar",
        )
        for i in ["a", "b", "c", "oidc", "d"]:
            UserSocialAuth.objects.create(user=self.sso_user, provider=i, uid=str(uuid4()))

    def tearDown(self):
        self.sso_user.delete()

    def test_without_fix_paramter(self):
        base = Mock()
        before = UserSocialAuth.objects.all().filter(user=self.sso_user).count()
        Command.handle(base, fix=False)
        after = UserSocialAuth.objects.all().filter(user=self.sso_user).count()
        self.assertEqual(before, after)
        base.stdout.write.assert_any_call(
            "NOTE: Won't change the DB unless --fix is passed as a parameter"
        )

    def test_with_fix_paramter(self):
        base = Mock()
        Command.handle(base, fix=True)
        counter = UserSocialAuth.objects.all().filter(user=self.sso_user).count()
        self.assertEqual(counter, 1)
        base.stdout.write.assert_called_with("4 SSO association removed.")
        remaining_provider = UserSocialAuth.objects.get(user=self.sso_user).provider
        self.assertEqual(remaining_provider, "oidc")
