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

"""
Tests for UserResponseSerializer, verifying nullable organization handling.
"""

from unittest.mock import Mock
from uuid import uuid4

from django.test import TestCase

from ansible_ai_connect.users.serializers import UserResponseSerializer


class UserResponseSerializerTest(TestCase):
    def _make_user(self, organization=None):
        """Create a mock user with the fields required by UserResponseSerializer."""
        user = Mock()
        user.email = "test@example.com"
        user.external_username = "testuser"
        user.family_name = "Doe"
        user.given_name = "John"
        user.organization = organization
        user.rh_org_has_subscription = False
        user.rh_user_has_seat = False
        user.rh_user_is_org_admin = False
        user.username = "testuser"
        user.userplan_set = []
        user.uuid = uuid4()
        return user

    def test_serializer_with_null_organization(self):
        """Verify that a user with organization=None serializes correctly."""
        user = self._make_user(organization=None)
        serializer = UserResponseSerializer(user)
        data = serializer.data

        self.assertIn("organization", data)
        self.assertIsNone(data["organization"])
        self.assertEqual(data["username"], "testuser")

    def test_serializer_with_valid_organization(self):
        """Verify that a user with a valid organization serializes correctly."""
        org = Mock()
        org.id = 12345
        org.telemetry_opt_out = False

        user = self._make_user(organization=org)
        serializer = UserResponseSerializer(user)
        data = serializer.data

        self.assertIn("organization", data)
        self.assertIsNotNone(data["organization"])
        self.assertEqual(data["organization"]["id"], 12345)
