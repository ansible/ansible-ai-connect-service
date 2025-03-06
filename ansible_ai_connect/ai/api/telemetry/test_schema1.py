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

from unittest import mock

from django.test import override_settings

from ansible_ai_connect.test_utils import WisdomServiceAPITestCaseBaseOIDC

from .schema1 import (
    ExplainPlaybookEvent,
    ExplainRoleEvent,
    GenerationPlaybookEvent,
    OneClickTrialStartedEvent,
    Schema1Event,
)


@override_settings(AUTHZ_BACKEND_TYPE="dummy")
@override_settings(WCA_SECRET_DUMMY_SECRETS="1981:valid")
class TestSchema1Event(WisdomServiceAPITestCaseBaseOIDC):
    def test_set_user(self):
        event1 = Schema1Event()
        event1.set_user(self.user)
        self.assertEqual(event1.rh_user_org_id, 1981)
        self.assertEqual(event1.groups, ["Group 1", "Group 2"])

    def test_set_request(self):
        m_request = mock.Mock()
        m_request.user = self.user
        m_request.path = "/trial"
        m_request.method = "POST"
        event1 = Schema1Event()
        event1.set_request(m_request)
        self.assertEqual(event1.request.path, "/trial")
        self.assertEqual(event1.request.method, "POST")

    def test_set_exception(self):
        event1 = Schema1Event()
        self.assertFalse(event1.exception)
        try:
            1 / 0
        except ZeroDivisionError as e:
            event1.set_exception(e)
        self.assertTrue(event1.exception)
        self.assertEqual(event1.response.exception, "division by zero")
        self.assertEqual(event1.problem, "division by zero")

    def test_as_dict(self):
        event1 = Schema1Event()
        as_dict = event1.as_dict()

        self.assertEqual(as_dict.get("event_name"), None)
        self.assertFalse(as_dict.get("exception"), False)

    def test_duration(self):
        event1 = Schema1Event()
        self.assertGreater(event1._created_at, 0)
        self.assertIsNone(event1.duration)
        self.assertIsNone(event1.timestamp)
        event1.finalize()
        self.assertGreater(event1.duration, 0)
        self.assertTrue(event1.timestamp)


@override_settings(AUTHZ_BACKEND_TYPE="dummy")
@override_settings(WCA_SECRET_DUMMY_SECRETS="1981:valid")
class TestOneClickTrialStartedEvent(WisdomServiceAPITestCaseBaseOIDC):

    def setUp(self):
        super().setUp()
        self.start_user_plan()

    def tearDown(self):
        super().tearDown()
        self.trial_plan.delete()

    def test_new_trial(self):
        event1 = OneClickTrialStartedEvent()
        self.assertEqual(event1.event_name, "oneClickTrialStarted")

    def test_new_trial_record_plan(self):

        event1 = OneClickTrialStartedEvent()
        event1.set_user(self.user)
        self.assertTrue(isinstance(event1.plans, list))
        self.assertEqual(len(event1.plans), 1)
        self.assertEqual(event1.plans[0].name, "Some plan")
        self.assertTrue(event1.plans[0].created_at.startswith("20"))
        self.assertEqual(event1.plans[0].plan_id, self.trial_plan.id)
        self.assertEqual(event1.plan_ids, [self.trial_plan.id])


@override_settings(AUTHZ_BACKEND_TYPE="dummy")
@override_settings(WCA_SECRET_DUMMY_SECRETS="1981:valid")
class TestExplainPlaybookEvent(WisdomServiceAPITestCaseBaseOIDC):
    def test_base(self):
        event1 = ExplainPlaybookEvent()
        self.assertEqual(event1.event_name, "explainPlaybook")


@override_settings(AUTHZ_BACKEND_TYPE="dummy")
@override_settings(WCA_SECRET_DUMMY_SECRETS="1981:valid")
class TestExplainRoleEvent(WisdomServiceAPITestCaseBaseOIDC):
    def test_base(self):
        event1 = ExplainRoleEvent()
        self.assertEqual(event1.event_name, "explainRole")


@override_settings(AUTHZ_BACKEND_TYPE="dummy")
@override_settings(WCA_SECRET_DUMMY_SECRETS="1981:valid")
class TestGenerationPlaybookEvent(WisdomServiceAPITestCaseBaseOIDC):
    def test_base(self):
        event1 = GenerationPlaybookEvent()
        self.assertEqual(event1.event_name, "codegenPlaybook")
        self.assertFalse(event1.create_outline)
