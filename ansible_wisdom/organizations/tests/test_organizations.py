from unittest.mock import patch

from django.test import TestCase, override_settings

import ansible_wisdom.ai.feature_flags as feature_flags
from ansible_wisdom.organizations.models import Organization


class TestOrganization(TestCase):
    def test_org_with_telemetry_schema_2_opted_in(self):
        organization = Organization.objects.get_or_create(id=123, telemetry_opt_out=False)[0]
        self.assertFalse(organization.telemetry_opt_out)
        self.assertFalse(organization.is_schema_2_telemetry_enabled)

    def test_org_with_telemetry_schema_2_opted_out(self):
        organization = Organization.objects.get_or_create(id=123, telemetry_opt_out=True)[0]
        self.assertTrue(organization.telemetry_opt_out)
        self.assertFalse(organization.is_schema_2_telemetry_enabled)

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @patch.object(feature_flags, 'LDClient')
    def test_org_with_telemetry_schema_2_opted_in_with_feature_flag_override(self, LDClient):
        LDClient.return_value.variation.return_value = True
        organization = Organization.objects.get_or_create(id=123, telemetry_opt_out=True)[0]
        self.assertTrue(organization.telemetry_opt_out)
        self.assertTrue(organization.is_schema_2_telemetry_enabled)

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @patch.object(feature_flags, 'LDClient')
    def test_org_with_telemetry_schema_2_opted_in_with_feature_flag_no_override(self, LDClient):
        LDClient.return_value.variation.return_value = False
        organization = Organization.objects.get_or_create(id=123, telemetry_opt_out=True)[0]
        self.assertTrue(organization.telemetry_opt_out)
        self.assertFalse(organization.is_schema_2_telemetry_enabled)

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @patch.object(feature_flags, 'LDClient')
    def test_org_with_telemetry_schema_2_opted_out_with_feature_flag_override(self, LDClient):
        LDClient.return_value.variation.return_value = True
        organization = Organization.objects.get_or_create(id=123, telemetry_opt_out=False)[0]
        self.assertFalse(organization.telemetry_opt_out)
        self.assertTrue(organization.is_schema_2_telemetry_enabled)

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @patch.object(feature_flags, 'LDClient')
    def test_org_with_telemetry_schema_2_opted_out_with_feature_flag_no_override(self, LDClient):
        LDClient.return_value.variation.return_value = False
        organization = Organization.objects.get_or_create(id=123, telemetry_opt_out=False)[0]
        self.assertFalse(organization.telemetry_opt_out)
        self.assertFalse(organization.is_schema_2_telemetry_enabled)
