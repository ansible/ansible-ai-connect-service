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

from unittest import TestCase, mock
from unittest.mock import MagicMock, Mock

from django.test import override_settings
from segment import analytics

from ansible_ai_connect.ai.api.utils import segment_analytics_telemetry
from ansible_ai_connect.ai.api.utils.seated_users_allow_list import ALLOW_LIST
from ansible_ai_connect.ai.api.utils.segment import (
    base_send_segment_event,
    redact_seated_users_data,
    send_segment_event,
    send_segment_group,
)
from ansible_ai_connect.ai.api.utils.segment_analytics_telemetry import (
    get_segment_analytics_client,
)


class TestSegment(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        analytics.send = False  # do not send data to segment from unit tests

    def test_redact_seated_users_data_first_level_parameter(self, *args):
        test_data = {
            # first level parameter should be redacted
            "exception": True,
            "problem": "_InactiveRpcError",
            "details": None,
        }

        expected_result = {
            "exception": True,
            "problem": "_InactiveRpcError",
        }

        self.assertEqual(
            redact_seated_users_data(test_data, ALLOW_LIST["postprocess"]), expected_result
        )

    def test_redact_seated_users_data_with_array_parameter(self, *args):
        test_data = {
            # first level parameter should be redacted
            "taskCount": 1,
            "tasks": [
                {
                    "collection": "ansible.builtin",
                    "module": "ansible.builtin.shell",
                    "name": "i*** r*** o*** r***",
                    "prediction": "    ansible.builtin.shell: yum install -y cargo\n ",
                }
            ],
        }

        expected_result = {
            "taskCount": 1,
            "tasks": [
                {
                    "collection": "ansible.builtin",
                    "module": "ansible.builtin.shell",
                }
            ],
        }

        self.assertEqual(
            redact_seated_users_data(test_data, ALLOW_LIST["completion"]), expected_result
        )

    def test_redact_seated_users_data_with_array_and_several_items_in_it_parameter(self, *args):
        test_data = {
            # first level parameter should be redacted
            "taskCount": 1,
            "tasks": [
                {
                    "collection": "ansible.builtin",
                    "module": "ansible.builtin.shell",
                    "name": "i*** r*** o*** r***",
                    "prediction": "    ansible.builtin.shell: yum install -y cargo",
                },
                {
                    "collection": "ansible.builtin",
                    "module": "ansible.builtin.shell",
                    "name": "run an incremental deploy for ibm qradar",
                    "prediction": 'ansible.builtin.shell: "cd {{ unarchive_dest }}',
                },
            ],
            "suggestionId": "5e917739-3ba1-4253-9a06-00470e0d9977",
        }

        expected_result = {
            "taskCount": 1,
            "tasks": [
                {
                    "collection": "ansible.builtin",
                    "module": "ansible.builtin.shell",
                },
                {
                    "collection": "ansible.builtin",
                    "module": "ansible.builtin.shell",
                },
            ],
            "suggestionId": "5e917739-3ba1-4253-9a06-00470e0d9977",
        }

        self.assertEqual(
            redact_seated_users_data(test_data, ALLOW_LIST["completion"]), expected_result
        )

    def test_redact_seated_users_data_with_nested_array_parameter(self, *args):
        test_data = {
            "request": {
                "instances": [
                    {
                        "prompt": "- name: the task name",
                        "organization_id": 876,
                        "rh_user_has_seat": True,
                        "context": "- hosts: all\n  tasks:\n",
                        "suggestionId": "5ce0e9a5-5ffa-654b-cee0-1238041fb31a",
                        "userId": "ce5eb017-d917-47b3-a5f7-ee764277ff6e",
                    }
                ]
            },
        }

        expected_result = {
            "request": {
                "instances": [
                    {
                        "organization_id": 876,
                        "rh_user_has_seat": True,
                        "suggestionId": "5ce0e9a5-5ffa-654b-cee0-1238041fb31a",
                        "userId": "ce5eb017-d917-47b3-a5f7-ee764277ff6e",
                    }
                ]
            },
        }

        self.assertEqual(
            redact_seated_users_data(test_data, ALLOW_LIST["prediction"]), expected_result
        )

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_send_segment_event_commercial_forbidden_event(self, *args):
        g = Mock()
        g.values_list = MagicMock(return_value=[])
        user = Mock(rh_user_has_seat=True, groups=g)
        user.userplan_set.all.return_value = []
        event = {
            "rh_user_has_seat": True,
        }

        with self.assertLogs(logger="root") as log:
            send_segment_event(event, "someUnallowedFeedback", user)
            self.assertEqual(
                log.output[0],
                "ERROR:ansible_ai_connect.ai.api.utils.segment:It is not allowed to track"
                + " someUnallowedFeedback events for seated users",
            )

    @mock.patch("ansible_ai_connect.ai.api.utils.segment.analytics.track")
    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_send_segment_event_community_user(self, track_method):
        g = Mock()
        g.values_list = MagicMock(return_value=[])
        user = Mock(rh_user_has_seat=False, groups=g)
        user.userplan_set.all.return_value = []
        event = {
            "rh_user_has_seat": False,
            "exception": "SomeException",
            "details": "Some details",
        }
        send_segment_event(event, "postprocess", user)
        argument = track_method.call_args[0][2]

        self.assertEqual(argument["details"], "Some details")
        self.assertEqual(argument["exception"], "SomeException")

    @mock.patch("ansible_ai_connect.ai.api.utils.segment.analytics.track")
    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_send_segment_event_seated_user(self, track_method):
        g = Mock()
        g.values_list = MagicMock(return_value=[])
        user = Mock(rh_user_has_seat=True, groups=g)
        user.userplan_set.all.return_value = []
        event = {
            "rh_user_has_seat": True,
            "exception": "SomeException",
            "details": "Some details",
        }
        send_segment_event(event, "postprocess", user)
        argument = track_method.call_args[0][2]

        self.assertEqual(argument.get("details"), None)
        self.assertEqual(argument.get("exception"), "SomeException")

    def test_redact_contentmatches_response_data(self, *args):
        test_data = {
            "exception": False,
            "modelName": "org-model-id",
            "problem": None,
            "response": {
                "contentmatches": [
                    {
                        "contentmatch": [
                            {
                                "repo_name": "robertdebock.nginx",
                                "repo_url": "https://galaxy.ansible.com/robertdebock/nginx",
                                "path": "tasks/main.yml",
                                "license": "apache-2.0",
                                "score": 0.0,
                                "data_source_description": "Ansible Galaxy roles",
                            }
                        ]
                    }
                ]
            },
            "metadata": [{"encode_duration": 1000, "search_duration": 2000}],
        }

        expected_result = {
            "exception": False,
            "modelName": "org-model-id",
            "problem": None,
            "metadata": [{"encode_duration": 1000, "search_duration": 2000}],
        }

        self.assertEqual(
            redact_seated_users_data(test_data, ALLOW_LIST["contentmatch"]), expected_result
        )

    def test_redact_trialExpired_response_data(self, *args):
        test_data = {
            "type": "prediction",
            "modelName": "org-model-id",
            "suggestionId": "1",
            "rh_user_has_seat": True,
            "rh_user_org_id": 101,
            "groups": ["g1", "g2"],
        }

        expected_result = {
            "type": "prediction",
            "suggestionId": "1",
            "modelName": "org-model-id",
            "groups": ["g1", "g2"],
            "rh_user_has_seat": True,
            "rh_user_org_id": 101,
        }

        self.assertEqual(
            redact_seated_users_data(test_data, ALLOW_LIST["trialExpired"]), expected_result
        )

    def test_redact_chat_operational_event(self, *args):
        test_data = {
            "type": "chatOperationalEvent",
            "modelName": "org-model-id",
            "rh_user_has_seat": True,
            "rh_user_org_id": 101,
            "anything": "whatever",
            "chat_prompt": "user_query_should_be_filtered",  # This should be filtered out
        }

        expected_result = {
            # Only fields in the explicit allow list should be preserved
            "modelName": "org-model-id",
            "rh_user_has_seat": True,
            "rh_user_org_id": 101,
            # Note: "type", "anything", and "chat_prompt" are filtered out
            # since they're not in the allow list
        }

        self.assertEqual(
            redact_seated_users_data(test_data, ALLOW_LIST["chatOperationalEvent"]), expected_result
        )

    def test_redact_chat_feedback_event(self, *args):
        test_data = {
            "type": "chatFeedbackEvent",
            "modelName": "org-model-id",
            "rh_user_has_seat": True,
            "rh_user_org_id": 101,
            "anything": "whatever",
        }

        expected_result = {
            "type": "chatFeedbackEvent",
            "modelName": "org-model-id",
            "rh_user_has_seat": True,
            "rh_user_org_id": 101,
            "anything": "whatever",  # Any properties won't be redacted for chatFeedbackEvent
        }

        self.assertEqual(
            redact_seated_users_data(test_data, ALLOW_LIST["chatFeedbackEvent"]), expected_result
        )

    @mock.patch("ansible_ai_connect.ai.api.utils.segment.analytics.group")
    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_send_segment_group(self, group_method):
        user = Mock()
        group_type = "RH Org"
        group_value = "1234"
        send_segment_group("rhsso-1234", group_type, group_value, user)
        group_method.assert_called_once()
        traits = group_method.call_args.args[2]

        self.assertEqual(traits, {"group_type": group_type, "group_value": group_value})

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_segment_client_in_use(self):
        g = Mock()
        g.values_list = MagicMock(return_value=[])
        user = Mock(rh_user_has_seat=False, groups=g)
        event = {
            "rh_user_has_seat": False,
            "exception": "SomeException",
            "details": "Some details",
        }
        segment_analytics_telemetry.write_key = "testWriteKey"
        client = Mock(wraps=get_segment_analytics_client())
        base_send_segment_event(event, "postprocess", user, client)
        client.track.assert_called()

    @mock.patch("ansible_ai_connect.ai.api.utils.segment.analytics.track")
    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_send_segment_plans(self, track_method):
        user = Mock()
        user.groups.values_list.return_value = []
        userplan = Mock()
        userplan.accept_marketing = True
        userplan.created_at = "Some date"
        userplan.expired_at = "Some other date"
        userplan.is_active = True
        userplan.plan.name = "Trial plan"
        userplan.plan.id = 1
        user.userplan_set.all.return_value = [userplan]
        send_segment_event({}, "postprocess", user)
        user, event_name, event = track_method.call_args[0]
        self.assertEqual(
            event["plans"][0],
            {
                "accept_marketing": True,
                "created_at": "Some date",
                "expired_at": "Some other date",
                "is_active": True,
                "name": "Trial plan",
                "plan_id": 1,
            },
        )
