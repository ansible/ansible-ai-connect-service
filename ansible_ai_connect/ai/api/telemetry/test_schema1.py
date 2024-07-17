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

from datetime import datetime, timedelta
from unittest import TestCase, mock

from .schema1 import OneClickTrialStartedEvent, Schema1Event


class TestSchema1Event(TestCase):
    def test_set_user(self):
        m_user = mock.Mock()
        m_user.rh_user_has_seat = True
        m_user.org_id = 123
        m_user.groups.values_list.return_value = ["mecano"]
        event1 = Schema1Event()
        event1.set_user(m_user)
        self.assertEqual(event1.rh_user_has_seat, True)
        self.assertEqual(event1.rh_user_org_id, 123)
        self.assertEqual(event1.groups, ["mecano"])

    def test_set_request(self):
        m_request = mock.Mock()
        m_request.user.groups.values_list.return_value = []
        m_request.path = "/trial"
        m_request.method = "POST"
        event1 = Schema1Event()
        event1.set_request(m_request)
        self.assertEqual(event1.request.path, "/trial")
        self.assertEqual(event1.request.method, "POST")

    def test_as_dict(self):
        event1 = Schema1Event()
        as_dict = event1.as_dict()

        self.assertEqual(as_dict.get("event_name"), None)
        self.assertFalse(as_dict.get("exception"), False)


class TestOneClickTrialStartedEvent(TestCase):
    def test_new_trial(self):
        event1 = OneClickTrialStartedEvent()
        self.assertEqual(event1.event_name, "oneClickTrialStarted")

    def test_new_trial_record_plan(self):
        m_plan = mock.Mock()
        m_plan.plan.name = "Some plan"
        m_plan.plan.id = 12
        m_plan.created_at = str(datetime.now())
        m_plan.expired_at = str(datetime.now() + timedelta(days=30))
        m_plan.is_expired = False
        m_user = mock.Mock()
        m_user.groups.values_list.return_value = []
        m_user.userplan_set.all.return_value = [m_plan]
        event1 = OneClickTrialStartedEvent()
        event1.set_user(m_user)
        self.assertTrue(isinstance(event1.plans, list))
        self.assertEqual(len(event1.plans), 1)
        self.assertEqual(event1.plans[0].name, "Some plan")
        self.assertTrue(event1.plans[0].created_at.startswith("20"))
        self.assertEqual(event1.plans[0].plan_id, 12)
