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
from unittest.mock import patch

from django.test import override_settings

from ansible_ai_connect.ai.api.telemetry.schema2 import AnalyticsTelemetryEvents
from ansible_ai_connect.ai.api.telemetry.schema2_utils import (
    _oneclick_trial_event_build,
    oneclick_trial_event_send,
)
from ansible_ai_connect.ai.api.utils import segment_analytics_telemetry


class TestSchema2OneClickTrial(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        TestSchema2OneClickTrial._set_defaults()

    @staticmethod
    def _set_defaults():
        segment_analytics_telemetry.write_key = "testWriteKey"
        segment_analytics_telemetry.send = False

    def test_oneclick_trial_event_build(self):
        m_user = TestSchema2OneClickTrial.create_trial_user_plan()
        event = _oneclick_trial_event_build(m_user)
        self.assertTrue(isinstance(event.plans, list))
        self.assertEqual(len(event.plans), 1)
        self.assertEqual(event.plans[0].name, "Some plan")
        self.assertTrue(event.plans[0].created_at.startswith("20"))
        self.assertEqual(event.plans[0].id, 12)
        self.assertEqual(event.rh_user_org_id, 123)

    def test_oneclick_trial_event_build_error_no_org(self):
        m_user = TestSchema2OneClickTrial.create_trial_user_plan()
        m_user.organization = None
        with self.assertRaises(ValueError) as context:
            _oneclick_trial_event_build(m_user)
            self.assertTrue("This is broken" in str(context.exception))

    @override_settings(SEGMENT_ANALYTICS_WRITE_KEY="testWriteKey")
    @patch("ansible_ai_connect.ai.api.utils.segment_analytics_telemetry.base_send_segment_event")
    def test_oneclick_trial_event_send(self, mock_send):
        m_user = TestSchema2OneClickTrial.create_trial_user_plan()
        oneclick_trial_event_send(m_user)
        mock_send.assert_called_once()
        self.assertEqual(
            mock_send.call_args[0][1], AnalyticsTelemetryEvents.ONECLICK_TRIAL_STARTED.value
        )
        self.assertEqual(mock_send.call_args[0][2], m_user)

    @staticmethod
    def create_trial_user_plan():
        m_plan = mock.Mock()
        m_plan.plan.name = "Some plan"
        m_plan.plan.id = 12
        m_plan.created_at = str(datetime.now())
        m_plan.expired_at = str(datetime.now() + timedelta(days=30))
        m_plan.is_expired = False
        m_user = mock.Mock()
        m_org = mock.Mock()
        m_org.id = 123
        m_user.organization = m_org
        m_user.organization.has_telemetry_opt_out = False
        m_user.groups.values_list.return_value = []
        m_user.userplan_set.all.return_value = [m_plan]
        return m_user
