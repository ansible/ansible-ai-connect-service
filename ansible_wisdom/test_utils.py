from ast import literal_eval
from typing import Union
from unittest.mock import patch

from django.apps import apps
from django.test import TestCase


class WisdomLogAwareMixin:
    @staticmethod
    def searchInLogOutput(s, logs):
        for log in logs.output:
            if s in log:
                return True
        return False

    @staticmethod
    def extractSegmentEventsFromLog(logs):
        events = []
        for log in logs.output:
            if log.startswith('DEBUG:segment:queueing: '):
                obj = literal_eval(
                    log.replace('DEBUG:segment:queueing: ', '')
                    .replace('\n', '')
                    .replace('DataSource.UNKNOWN', '0')
                    .replace('AnsibleType.UNKNOWN', '0')
                )
                events.append(obj)
        return events


class WisdomTestCase(TestCase):
    def assert_error_detail(self, r, code: str, message: str = None):
        r_code = r.data.get('message').code
        self.assertEqual(r_code, code)
        if message:
            r_message = r.data.get('message')
            self.assertEqual(r_message, message)


class WisdomServiceLogAwareTestCase(WisdomTestCase, WisdomLogAwareMixin):
    def assertInLog(self, s, logs):
        self.assertTrue(self.searchInLogOutput(s, logs), logs)

    def assertNotInLog(self, s, logs):
        self.assertFalse(self.searchInLogOutput(s, logs), logs)

    def assertSegmentTimestamp(self, log):
        segment_events = self.extractSegmentEventsFromLog(log)
        for event in segment_events:
            self.assertIsNotNone(event['timestamp'])

    def assert_segment_log(self, log, event: str, problem: Union[str, None], **kwargs):
        segment_events = self.extractSegmentEventsFromLog(log)
        self.assertTrue(len(segment_events) == 1)
        self.assertEqual(segment_events[0]["event"], event)
        if problem:
            self.assertEqual(segment_events[0]["properties"]["problem"], problem)
            self.assertEqual(
                segment_events[0]["properties"]["exception"], True if problem else False
            )
        for key, value in kwargs.items():
            self.assertEqual(segment_events[0]["properties"][key], value)


class WisdomAppsBackendMocking(WisdomTestCase):
    """
    Ensure that the apps backend are properly reinitialized between each tests and avoid
    potential side-effects.
    """

    def setUp(self):
        super().setUp()
        self.backend_patchers = {
            key: patch.object(apps.get_app_config('ai'), key, None)
            for key in ["_wca_client", "_ari_caller", "_seat_checker", "_wca_secret_manager"]
        }
        for key, mocker in self.backend_patchers.items():
            mocker.start()

    def tearDown(self):
        for patcher in self.backend_patchers.values():
            patcher.stop()
        super().tearDown()

    @staticmethod
    def mock_wca_client_with(mocked):
        apps.get_app_config('ai')._wca_client = mocked

    @staticmethod
    def mock_ari_caller_with(mocked):
        apps.get_app_config('ai')._ari_caller = mocked

    @staticmethod
    def mock_seat_checker_with(mocked):
        apps.get_app_config('ai')._seat_checker = mocked

    @staticmethod
    def mock_wca_secret_manager_with(mocked):
        apps.get_app_config('ai')._wca_secret_manager = mocked
