from unittest import TestCase, mock
from unittest.mock import MagicMock, Mock

from ai.api.utils import segment_analytics_telemetry
from ai.api.utils.seated_users_allow_list import ALLOW_LIST
from ai.api.utils.segment import (
    base_send_segment_event,
    redact_seated_users_data,
    send_segment_event,
    send_segment_group,
)
from ai.api.utils.segment_analytics_telemetry import get_segment_analytics_client
from django.test import override_settings
from segment import analytics


class TestSegment(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        analytics.send = False  # do not send data to segment from unit tests

    def test_redact_seated_users_data_first_level_parameter(self, *args):
        test_data = {
            # first level parameter should be redacted
            'exception': True,
            'problem': '_InactiveRpcError',
            'details': None,
        }

        expected_result = {
            'exception': True,
            'problem': '_InactiveRpcError',
        }

        self.assertEqual(
            redact_seated_users_data(test_data, ALLOW_LIST['postprocess']), expected_result
        )

    def test_redact_seated_users_data_with_array_parameter(self, *args):
        test_data = {
            # first level parameter should be redacted
            'taskCount': 1,
            'tasks': [
                {
                    'collection': 'ansible.builtin',
                    'module': 'ansible.builtin.shell',
                    'name': 'i*** r*** o*** r***',
                    'prediction': '    ansible.builtin.shell: yum install -y cargo\n ',
                }
            ],
        }

        expected_result = {
            'taskCount': 1,
            'tasks': [
                {
                    'collection': 'ansible.builtin',
                    'module': 'ansible.builtin.shell',
                }
            ],
        }

        self.assertEqual(
            redact_seated_users_data(test_data, ALLOW_LIST['completion']), expected_result
        )

    def test_redact_seated_users_data_with_array_and_several_items_in_it_parameter(self, *args):
        test_data = {
            # first level parameter should be redacted
            'taskCount': 1,
            'tasks': [
                {
                    'collection': 'ansible.builtin',
                    'module': 'ansible.builtin.shell',
                    'name': 'i*** r*** o*** r***',
                    'prediction': '    ansible.builtin.shell: yum install -y cargo',
                },
                {
                    "collection": "ansible.builtin",
                    "module": "ansible.builtin.shell",
                    "name": "run an incremental deploy for ibm qradar",
                    "prediction": "ansible.builtin.shell: \"cd {{ unarchive_dest }}",
                },
            ],
            "suggestionId": "5e917739-3ba1-4253-9a06-00470e0d9977",
        }

        expected_result = {
            'taskCount': 1,
            'tasks': [
                {
                    'collection': 'ansible.builtin',
                    'module': 'ansible.builtin.shell',
                },
                {
                    'collection': 'ansible.builtin',
                    'module': 'ansible.builtin.shell',
                },
            ],
            "suggestionId": "5e917739-3ba1-4253-9a06-00470e0d9977",
        }

        self.assertEqual(
            redact_seated_users_data(test_data, ALLOW_LIST['completion']), expected_result
        )

    def test_redact_seated_users_data_with_nested_array_parameter(self, *args):
        test_data = {
            'request': {
                'instances': [
                    {
                        'prompt': '- name: the task name',
                        'organization_id': 876,
                        'rh_user_has_seat': True,
                        'context': '- hosts: all\n  tasks:\n',
                        'suggestionId': '5ce0e9a5-5ffa-654b-cee0-1238041fb31a',
                        'userId': 'ce5eb017-d917-47b3-a5f7-ee764277ff6e',
                    }
                ]
            },
        }

        expected_result = {
            'request': {
                'instances': [
                    {
                        'organization_id': 876,
                        'rh_user_has_seat': True,
                        'suggestionId': '5ce0e9a5-5ffa-654b-cee0-1238041fb31a',
                        'userId': 'ce5eb017-d917-47b3-a5f7-ee764277ff6e',
                    }
                ]
            },
        }

        self.assertEqual(
            redact_seated_users_data(test_data, ALLOW_LIST['prediction']), expected_result
        )

    def test_redact_seated_users_data_nested_parameter(self, *args):
        test_data = {
            # nested parameter should not be redacted
            'suggestionId': 'ce5eb017-d917-47b3-a5f7-ee764277ff6e',
            'attributions': [
                {
                    'repo_name': 'Repository_mock_name',
                    'path': '/some/path',
                    'ansible_type': 1,
                    'score': 1.5,
                },
            ],
        }

        expected_result = {
            'suggestionId': 'ce5eb017-d917-47b3-a5f7-ee764277ff6e',
            'attributions': [
                {
                    'ansible_type': 1,
                    'score': 1.5,
                    'repo_name': 'Repository_mock_name',
                    'path': '/some/path',
                },
            ],
        }

        self.assertEqual(
            redact_seated_users_data(test_data, ALLOW_LIST['attribution']), expected_result
        )

    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_send_segment_event_commercial_forbidden_event(self, *args):
        g = Mock()
        g.values_list = MagicMock(return_value=[])
        user = Mock(rh_user_has_seat=True, groups=g)
        event = {
            'rh_user_has_seat': True,
        }

        with self.assertLogs(logger='root') as log:
            send_segment_event(event, 'inlineSuggestionFeedback', user)
            self.assertEqual(
                log.output[0],
                'ERROR:ai.api.utils.segment:It is not allowed to track'
                + ' inlineSuggestionFeedback events for seated users',
            )

    @mock.patch("ai.api.utils.segment.analytics.track")
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_send_segment_event_community_user(self, track_method):
        g = Mock()
        g.values_list = MagicMock(return_value=[])
        user = Mock(rh_user_has_seat=False, groups=g)
        event = {
            'rh_user_has_seat': False,
            'exception': 'SomeException',
            'details': 'Some details',
        }
        send_segment_event(event, 'postprocess', user)
        argument = track_method.call_args[0][2]

        self.assertEqual(argument['details'], 'Some details')
        self.assertEqual(argument['exception'], 'SomeException')

    @mock.patch("ai.api.utils.segment.analytics.track")
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_send_segment_event_seated_user(self, track_method):
        g = Mock()
        g.values_list = MagicMock(return_value=[])
        user = Mock(rh_user_has_seat=True, groups=g)
        event = {
            'rh_user_has_seat': True,
            'exception': 'SomeException',
            'details': 'Some details',
        }
        send_segment_event(event, 'postprocess', user)
        argument = track_method.call_args[0][2]

        self.assertEqual(argument.get('details'), None)
        self.assertEqual(argument.get('exception'), 'SomeException')

    def test_redact_contentmatches_response_data(self, *args):
        test_data = {
            'exception': False,
            'modelName': 'org-model-id',
            'problem': None,
            'response': {
                'contentmatches': [
                    {
                        'contentmatch': [
                            {
                                'repo_name': 'robertdebock.nginx',
                                'repo_url': 'https://galaxy.ansible.com/robertdebock/nginx',
                                'path': 'tasks/main.yml',
                                'license': 'apache-2.0',
                                'score': 0.0,
                                'data_source_description': 'Ansible Galaxy roles',
                            }
                        ]
                    }
                ]
            },
            'metadata': [{'encode_duration': 1000, 'search_duration': 2000}],
        }

        expected_result = {
            'exception': False,
            'modelName': 'org-model-id',
            'problem': None,
            'metadata': [{'encode_duration': 1000, 'search_duration': 2000}],
        }

        self.assertEqual(
            redact_seated_users_data(test_data, ALLOW_LIST['contentmatch']), expected_result
        )

    @mock.patch("ai.api.utils.segment.analytics.group")
    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_send_segment_group(self, group_method):
        user = Mock()
        group_type = 'RH Org'
        group_value = '1234'
        send_segment_group('rhsso-1234', group_type, group_value, user)
        group_method.assert_called_once()
        traits = group_method.call_args.args[2]

        self.assertEqual(traits, {'group_type': group_type, 'group_value': group_value})

    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_segment_client_in_use(self):
        g = Mock()
        g.values_list = MagicMock(return_value=[])
        user = Mock(rh_user_has_seat=False, groups=g)
        event = {
            'rh_user_has_seat': False,
            'exception': 'SomeException',
            'details': 'Some details',
        }
        segment_analytics_telemetry.write_key = "testWriteKey"
        client = Mock(wraps=get_segment_analytics_client())
        base_send_segment_event(event, 'postprocess', user, client)
        client.track.assert_called()
