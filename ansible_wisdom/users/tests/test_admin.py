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

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.test import TestCase


class TestWisdomUserAdmin(TestCase):
    def test_search_fields_includes_uuid(self):
        wisdom_admin = admin.site._registry[get_user_model()]
        expected_search_fields = UserAdmin.search_fields + ('uuid',)
        self.assertEqual(wisdom_admin.search_fields, expected_search_fields)
