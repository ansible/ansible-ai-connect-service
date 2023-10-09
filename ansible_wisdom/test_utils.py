from ast import literal_eval
from unittest import TestCase


class WisdomLogWarenessMixin:
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


class WisdomServiceLogAwareTestCase(TestCase, WisdomLogWarenessMixin):
    pass
