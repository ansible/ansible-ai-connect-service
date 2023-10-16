from unittest import TestCase, mock
from unittest.mock import MagicMock, Mock

from ai.api.utils.seated_users_allow_list import ALLOW_LIST
from ai.api.utils.segment import redact_seated_users_data, send_segment_event
from django.core.exceptions import PermissionDenied
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

    def test_redact_seated_users_data_nested_parameter(self, *args):
        test_data = {
            # nested parameter should be redacted
            'suggestionId': 'ce5eb017-d917-47b3-a5f7-ee764277ff6e',
            'attributions': {
                'repo_name': 'Repository_mock_name',
                'path': '/some/path',
                'ansible_type': 1,
                'score': 1.5,
            },
        }

        expected_result = {
            'suggestionId': 'ce5eb017-d917-47b3-a5f7-ee764277ff6e',
            'attributions': {
                'ansible_type': 1,
                'score': 1.5,
            },
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

        self.assertRaises(
            PermissionDenied, send_segment_event, event, 'inlineSuggestionFeedback', user
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
