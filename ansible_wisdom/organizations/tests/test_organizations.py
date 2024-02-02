from unittest.mock import patch

import ai.feature_flags as feature_flags
from django.test import TestCase, override_settings
from organizations.models import Organization


class TestIsOrgLightspeedSubscriber(TestCase):
    def test_org_with_telemetry_schema_2_enabled(self):
        organization = Organization.objects.get_or_create(id=123, telemetry_opt_out=True)[0]
        self.assertFalse(organization.is_schema_2_telemetry_override_enabled)

    def test_org_with_telemetry_schema_2_disabled(self):
        organization = Organization.objects.get_or_create(id=123, telemetry_opt_out=False)[0]
        self.assertFalse(organization.is_schema_2_telemetry_override_enabled)

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @patch.object(feature_flags, 'LDClient')
    def test_org_with_telemetry_schema_2_disabled_with_feature_flags(self, LDClient):
        LDClient.return_value.variation.return_value = ''
        organization = Organization.objects.get_or_create(id=123, telemetry_opt_out=False)[0]
        self.assertFalse(organization.is_schema_2_telemetry_override_enabled)

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @patch.object(feature_flags, 'LDClient')
    def test_org_with_telemetry_schema_2_disabled_with_feature_flags_no_override(self, LDClient):
        LDClient.return_value.variation.return_value = '999'
        organization = Organization.objects.get_or_create(id=123, telemetry_opt_out=False)[0]
        self.assertFalse(organization.is_schema_2_telemetry_override_enabled)

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @patch.object(feature_flags, 'LDClient')
    def test_org_with_telemetry_schema_2_disabled_with_feature_flags_with_override(self, LDClient):
        LDClient.return_value.variation.return_value = '123'
        organization = Organization.objects.get_or_create(id=123, telemetry_opt_out=False)[0]
        self.assertTrue(organization.is_schema_2_telemetry_override_enabled)

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @patch.object(feature_flags, 'LDClient')
    def test_org_with_telemetry_schema_2_disabled_with_feature_flags_with_overrides(self, LDClient):
        LDClient.return_value.variation.return_value = '000,999,123'
        organization = Organization.objects.get_or_create(id=123, telemetry_opt_out=False)[0]
        self.assertTrue(organization.is_schema_2_telemetry_override_enabled)
