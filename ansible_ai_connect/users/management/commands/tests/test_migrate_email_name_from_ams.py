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
from django.test import override_settings

from ansible_ai_connect.test_utils import WisdomServiceAPITestCaseBaseOIDC

User = get_user_model()


@override_settings(AUTHZ_BACKEND_TYPE="dummy")
class TestMigrate(WisdomServiceAPITestCaseBaseOIDC):
    def call_command(self, *args, **kwargs):
        out = StringIO()
        call_command(
            "migrate_email_name_from_ams",
            *args,
            stdout=out,
            stderr=StringIO(),
            **kwargs,
        )
        return out.getvalue()

    def test_migrate(self):
        original = (self.user.email, self.user.given_name, self.user.family_name)

        out = self.call_command()
        self.assertIn("1 users migrated", out)
        self.user = User.objects.get(id=self.user.id)
        self.assertNotEqual(
            original, (self.user.email, self.user.given_name, self.user.family_name)
        )
        self.assertEqual(self.user.given_name, "Robert")
