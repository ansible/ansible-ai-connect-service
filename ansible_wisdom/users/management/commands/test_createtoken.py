#!/usr/bin/env python3

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from oauth2_provider.models import AccessToken

from ansible_wisdom.organizations.models import Organization


class TestCreateToken(TestCase):
    def tearDown(self):
        User = get_user_model()
        AccessToken.objects.filter(token="test-token").delete()
        User.objects.filter(username="my-test-token-user").delete()
        Organization.objects.filter(id=12345).delete()

    def call_command(self, *args, **kwargs):
        out = StringIO()
        call_command(
            "createtoken",
            *args,
            stdout=out,
            stderr=StringIO(),
            **kwargs,
        )
        return out.getvalue()

    def test_empty_parameter(self):
        with self.assertRaises(CommandError) as e:
            self.call_command()
            self.assertContain(e.msg, "Cannot find user")

    def test_with_extra_parameters(self):
        self.call_command(
            "--token-name",
            "test-token",
            "--username",
            "my-test-token-user",
            "--create-user",
            "--organization-id=12345",
        )
        User = get_user_model()
        new_user = User.objects.filter(username="my-test-token-user")[0]
        self.assertTrue(new_user.organization.id, 12345)
        self.assertTrue(AccessToken.objects.filter(token="test-token").exists())
