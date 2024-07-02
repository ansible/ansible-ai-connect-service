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


from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from ansible_ai_connect.users.models import Plan
from ansible_ai_connect.users.tests.test_users import create_user


class Plans(TestCase):
    def test_plan(self):
        u = create_user()
        demo_plan, _ = Plan.objects.get_or_create(name="demo_90_days", expires_after="90 days")
        u.plans.add(demo_plan)
        self.assertEqual(u.plans.all().first().name, "demo_90_days")

        # Ensure we don't duplicate the record, note this behavior may change later
        # if we want to allow multiple demo periods for a single user
        u.plans.add(demo_plan)
        self.assertEqual(len(list(u.plans.all())), 1)

        self.assertEqual(len(u.userplan_set.all()), 1)

        my_sub = u.userplan_set.first()

        self.assertGreater(
            my_sub.expired_at - timezone.now(), timedelta(days=89, hours=23, minutes=59)
        )

        self.assertTrue(my_sub.is_active)

        my_sub.expired_at = timezone.now() - timedelta(days=1)
        self.assertFalse(my_sub.is_active)

        # Make it unlimited
        my_sub.expired_at = None
        self.assertTrue(my_sub.is_active)
