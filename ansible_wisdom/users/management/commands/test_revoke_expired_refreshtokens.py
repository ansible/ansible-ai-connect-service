#!/usr/bin/env python3

# Copyright (c) 2013, Massimiliano Pippi, Federico Frenguelli and contributors
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.


import datetime
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.utils import timezone
from oauth2_provider.models import (
    get_access_token_model,
    get_application_model,
    get_refresh_token_model,
)
from oauth2_provider.settings import oauth2_settings

Application = get_application_model()
AccessToken = get_access_token_model()
RefreshToken = get_refresh_token_model()
UserModel = get_user_model()


# Note: Tests based on the django-oauth-toolkit test-suite
class BaseTest(TestCase):
    factory = RequestFactory()

    @classmethod
    def setUpTestData(cls):
        cls.test_user = UserModel.objects.create_user("test_user", "test@example.com", "123456")
        cls.dev_user = UserModel.objects.create_user("dev_user", "dev@example.com", "123456")

        cls.application = Application.objects.create(
            name="Test Application",
            redirect_uris="http://localhost http://example.com http://example.org",
            user=cls.dev_user,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            client_secret="foobar",
        )
        tok = AccessToken.objects.create(
            user=cls.test_user,
            token="1234567890",
            application=cls.application,
            expires=timezone.now() + datetime.timedelta(days=1),
            scope="read write",
        )
        t = RefreshToken.objects.create(
            user=cls.test_user, token="999999999", application=cls.application, access_token=tok
        )
        t.created = timezone.now() - datetime.timedelta(
            seconds=oauth2_settings.REFRESH_TOKEN_EXPIRE_SECONDS + 1
        )
        t.save()


class TestRevokeExpiredRefreshTokens(BaseTest):
    def call_command(self, *args, **kwargs):
        out = StringIO()
        call_command(
            "revoke_expired_refreshtokens",
            *args,
            stdout=out,
            stderr=StringIO(),
            **kwargs,
        )
        return out.getvalue()

    def test_dry_run(self):
        out = self.call_command("--dry-run")
        self.assertIn("Deleting the 1 refreshtoken", out)
        self.assertIn("Doing nothing", out)
        count = RefreshToken.objects.all().filter(revoked__isnull=True).count()
        self.assertEqual(count, 1)

    def test_regular(self):
        count_before = RefreshToken.objects.all().filter(revoked__isnull=True).count()
        out = self.call_command()
        self.assertIn("Deleting the 1 refreshtoken", out)
        count_after = RefreshToken.objects.all().filter(revoked__isnull=False).count()
        self.assertEqual(count_before, count_after)
