from ast import literal_eval
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

    def assertInLog(self, s, logs):
        self.assertTrue(self.searchInLogOutput(s, logs), logs)

    def assertNotInLog(self, s, logs):
        self.assertFalse(self.searchInLogOutput(s, logs), logs)

    def assertSegmentTimestamp(self, log):
        segment_events = self.extractSegmentEventsFromLog(log)
        for event in segment_events:
            self.assertIsNotNone(event['timestamp'])


class WisdomServiceLogAwareTestCase(TestCase, WisdomLogAwareMixin):
    pass


class WisdomAppsBackendMocking(TestCase):
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
        self.mocked_backends = {
            key[1:]: mocker.start() for key, mocker in self.backend_patchers.items()
        }

    def tearDown(self):
        for patcher in self.backend_patchers.values():
            patcher.stop()
        super().tearDown()
