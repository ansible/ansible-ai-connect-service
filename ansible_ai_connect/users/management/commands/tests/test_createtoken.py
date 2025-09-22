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

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from oauth2_provider.models import AccessToken

from ansible_ai_connect.organizations.models import ExternalOrganization


class TestCreateToken(TestCase):
    def tearDown(self):
        User = get_user_model()
        AccessToken.objects.filter(token="test-token").delete()
        User.objects.filter(username="my-test-token-user").delete()
        ExternalOrganization.objects.filter(id=12345).delete()

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
