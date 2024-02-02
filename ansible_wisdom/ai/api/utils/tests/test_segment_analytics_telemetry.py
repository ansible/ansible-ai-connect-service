from unittest.mock import Mock, patch

import ai.feature_flags as feature_flags
from ai.api.tests.test_views import WisdomServiceAPITestCaseBase
from ai.api.utils import segment_analytics_telemetry
from ai.api.utils.analytics_telemetry_model import (
    AnalyticsProductFeedback,
    AnalyticsTelemetryEvents,
)
from ai.api.utils.segment_analytics_telemetry import (
    get_segment_analytics_client,
    send_segment_analytics_error_event,
    send_segment_analytics_event,
)
from attr import asdict
from django.test import override_settings
from organizations.models import Organization


class TestSegmentAnalyticsTelemetry(WisdomServiceAPITestCaseBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        TestSegmentAnalyticsTelemetry._set_defaults()

    def setUp(self):
        super().setUp()
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=123)[0]
        self.user.organization.telemetry_opt_out = False

    @staticmethod
    def on_segment_error(self, error, items):
        pass

    @staticmethod
    def _set_defaults():
        segment_analytics_telemetry.write_key = "testWriteKey"
        segment_analytics_telemetry.debug = True
        segment_analytics_telemetry.gzip = True
        segment_analytics_telemetry.host = "localhost"
        segment_analytics_telemetry.on_error = TestSegmentAnalyticsTelemetry.on_segment_error
        segment_analytics_telemetry.send = False
        segment_analytics_telemetry.sync_mode = False
        segment_analytics_telemetry.timeout = 10

    def test_get_segment_analytics_client(self):
        client = get_segment_analytics_client()
        self.assertEqual(client.write_key, "testWriteKey")
        self.assertEqual(client.debug, True)
        self.assertEqual(client.gzip, True)
        self.assertEqual(client.host, "localhost")
        self.assertEqual(client.on_error, TestSegmentAnalyticsTelemetry.on_segment_error)
        self.assertEqual(client.send, False)
        self.assertEqual(client.sync_mode, False)
        self.assertEqual(client.timeout, 10)

    @patch("ai.api.utils.segment_analytics_telemetry.send_segment_event")
    def test_send_segment_analytics_error_value(self, send_segment_event):
        error = ValueError()
        self._assert_segment_analytics_error_sent(error, send_segment_event)

    @patch("ai.api.utils.segment_analytics_telemetry.send_segment_event")
    def test_send_segment_analytics_error_type(self, send_segment_event):
        error = TypeError()
        self._assert_segment_analytics_error_sent(error, send_segment_event)

    def _assert_segment_analytics_error_sent(self, error, send_segment_event):
        send_segment_analytics_error_event("event_name", error, self.user)
        error_event_payload = {
            "error_type": "analytics_telemetry_error",
            "details": dict(event_name="event_name", error=error.__repr__()),
        }
        send_segment_event.assert_called_with(
            error_event_payload, "analyticsTelemetryError", self.user
        )

    @patch("ai.api.utils.segment_analytics_telemetry.base_send_segment_event")
    @override_settings(SEGMENT_ANALYTICS_WRITE_KEY="testWriteKey")
    @override_settings(TELEMETRY_SCHEMA_2_ENABLED=True)
    def test_send_segment_analytics_event(self, base_send_segment_event):
        analytics_event_object = AnalyticsProductFeedback(3, 123)
        payload = Mock(return_value=analytics_event_object)
        send_segment_analytics_event(AnalyticsTelemetryEvents.PRODUCT_FEEDBACK, payload, self.user)
        payload.assert_called()
        base_send_segment_event.assert_called_with(
            asdict(analytics_event_object),
            AnalyticsTelemetryEvents.PRODUCT_FEEDBACK.value,
            self.user,
            get_segment_analytics_client(),
        )

    @patch("ai.api.utils.segment_analytics_telemetry.send_segment_event")
    @override_settings(SEGMENT_ANALYTICS_WRITE_KEY="testWriteKey")
    @override_settings(TELEMETRY_SCHEMA_2_ENABLED=True)
    def test_send_segment_analytics_event_error_validation(self, send_segment_event):
        payload = Mock(side_effect=ValueError)
        send_segment_analytics_event(AnalyticsTelemetryEvents.PRODUCT_FEEDBACK, payload, self.user)
        payload.assert_called()
        error_event_payload = {
            "error_type": "analytics_telemetry_error",
            "details": dict(
                event_name=AnalyticsTelemetryEvents.PRODUCT_FEEDBACK.value,
                error=ValueError().__repr__(),
            ),
        }
        send_segment_event.assert_called_with(
            error_event_payload, "analyticsTelemetryError", self.user
        )

    @patch("ai.api.utils.segment_analytics_telemetry.base_send_segment_event")
    @override_settings(TELEMETRY_SCHEMA_2_ENABLED=True)
    def test_send_segment_analytics_event_error_not_write_key(self, base_send_segment_event):
        self._assert_event_not_sent(base_send_segment_event)

    @patch("ai.api.utils.segment_analytics_telemetry.base_send_segment_event")
    @override_settings(SEGMENT_ANALYTICS_WRITE_KEY="testWriteKey")
    @override_settings(TELEMETRY_SCHEMA_2_ENABLED=True)
    def test_send_segment_analytics_event_error_user_no_seat(self, base_send_segment_event):
        self.user.rh_user_has_seat = False
        self._assert_event_not_sent(base_send_segment_event)

    @patch("ai.api.utils.segment_analytics_telemetry.base_send_segment_event")
    @override_settings(SEGMENT_ANALYTICS_WRITE_KEY="testWriteKey")
    @override_settings(TELEMETRY_SCHEMA_2_ENABLED=False)
    def test_send_segment_analytics_event_error_no_telemetry_enabled(self, base_send_segment_event):
        self._assert_event_not_sent(base_send_segment_event)

    @patch("ai.api.utils.segment_analytics_telemetry.base_send_segment_event")
    @override_settings(SEGMENT_ANALYTICS_WRITE_KEY="testWriteKey")
    @override_settings(TELEMETRY_SCHEMA_2_ENABLED=True)
    def test_send_segment_analytics_event_error_no_org(self, base_send_segment_event):
        self.user.organization = None
        self._assert_event_not_sent(base_send_segment_event)

    @patch("ai.api.utils.segment_analytics_telemetry.base_send_segment_event")
    @override_settings(SEGMENT_ANALYTICS_WRITE_KEY="testWriteKey")
    @override_settings(TELEMETRY_SCHEMA_2_ENABLED=True)
    def test_send_segment_analytics_event_error_no_org_telemetry_enabled(
        self, base_send_segment_event
    ):
        self.user.organization.telemetry_opt_out = True
        self._assert_event_not_sent(base_send_segment_event)

    @override_settings(SEGMENT_ANALYTICS_WRITE_KEY="testWriteKey")
    @override_settings(TELEMETRY_SCHEMA_2_ENABLED=False)
    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @patch("ai.api.utils.segment_analytics_telemetry.base_send_segment_event")
    @patch.object(feature_flags, 'LDClient')
    def test_send_segment_analytics_event_no_telemetry_enabled_with_override(
        self, base_send_segment_event, LDClient
    ):
        LDClient.return_value.variation.return_value = str(self.user.organization.id)
        self._assert_event_sent(base_send_segment_event)

    @override_settings(SEGMENT_ANALYTICS_WRITE_KEY="testWriteKey")
    @override_settings(TELEMETRY_SCHEMA_2_ENABLED=True)
    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @patch("ai.api.utils.segment_analytics_telemetry.base_send_segment_event")
    @patch.object(feature_flags, 'LDClient')
    def test_send_segment_analytics_event_no_org_telemetry_enabled_with_override(
        self, base_send_segment_event, LDClient
    ):
        LDClient.return_value.variation.return_value = str(self.user.organization.id)
        self.user.organization.telemetry_opt_out = True
        self._assert_event_sent(base_send_segment_event)

    def _assert_event_sent(self, base_send_segment_event):
        payload = Mock(return_value=AnalyticsProductFeedback(3, 123))
        send_segment_analytics_event(AnalyticsTelemetryEvents.PRODUCT_FEEDBACK, payload, self.user)
        payload.assert_not_called()
        base_send_segment_event.assert_called()

    def _assert_event_not_sent(self, base_send_segment_event):
        payload = Mock(return_value=AnalyticsProductFeedback(3, 123))
        send_segment_analytics_event(AnalyticsTelemetryEvents.PRODUCT_FEEDBACK, payload, self.user)
        payload.assert_not_called()
        base_send_segment_event.assert_not_called()
