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

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.test import RequestFactory, TestCase
from django.urls import resolve, reverse

from ansible_ai_connect.main.permissions import IsRHInternalUser, IsTestUser


class TestIsRHInternalUser(TestCase):
    def setUp(self):
        super().setUp()

        self.permission = IsRHInternalUser()

        payload = {
            "query": "Hello",
        }
        self.request = RequestFactory().post(reverse("chat"), payload, format="json")

        self.non_rh_user = get_user_model().objects.create_user(
            username="non-rh-user",
            password="non-rh-password",
            email="non-rh-user@email.com",
            rh_internal=False,
        )
        self.rh_user = get_user_model().objects.create_user(
            username="rh-user",
            password="rh-password",
            email="rh-user@redhat.com",
            rh_internal=True,
        )

    def tearDown(self):
        self.non_rh_user.delete()
        self.rh_user.delete()

    def get_permission(self, user):
        self.request.user = user
        return self.permission.has_permission(self.request, resolve(reverse("chat")))

    def test_permission_with_rh_user(self):
        self.client.force_login(user=self.rh_user)
        r = self.get_permission(self.rh_user)
        self.assertTrue(r)

    def test_permission_with_non_rh_user(self):
        self.client.force_login(user=self.non_rh_user)
        r = self.get_permission(self.non_rh_user)
        self.assertFalse(r)

    def test_permission_with_anonymous_user(self):
        r = self.get_permission(AnonymousUser())
        self.assertFalse(r)


class TestIsTestUser(TestCase):
    def setUp(self):
        super().setUp()

        self.permission = IsTestUser()

        payload = {
            "query": "Hello",
        }
        self.request = RequestFactory().post(reverse("chat"), payload, format="json")

        self.non_rh_user = get_user_model().objects.create_user(
            username="non-rh-user",
            password="non-rh-password",
            email="non-rh-user@email.com",
            rh_internal=False,
        )
        self.test_group = Group(name="test")
        self.test_group.save()
        self.non_rh_test_user = get_user_model().objects.create_user(
            username="non-rh-test-user",
            password="non-rh-test-password",
            email="non-rh-test-user@email.com",
            rh_internal=False,
        )
        self.non_rh_test_user.groups.add(self.test_group)

    def tearDown(self):
        self.non_rh_user.delete()
        self.non_rh_test_user.delete()
        self.test_group.delete()

    def get_permission(self, user):
        self.request.user = user
        return self.permission.has_permission(self.request, resolve(reverse("chat")))

    def test_permission_with_non_rh_user(self):
        self.client.force_login(user=self.non_rh_user)
        r = self.get_permission(self.non_rh_user)
        self.assertFalse(r)

    def test_permission_with_non_rh_test_user(self):
        self.client.force_login(user=self.non_rh_test_user)
        r = self.get_permission(self.non_rh_test_user)
        self.assertTrue(r)

    def test_permission_with_anonymous_user(self):
        r = self.get_permission(AnonymousUser())
        self.assertFalse(r)
