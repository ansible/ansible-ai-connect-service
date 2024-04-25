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

from unittest.mock import patch

from django.test import TestCase, override_settings

import ansible_wisdom.ai.feature_flags as feature_flags
from ansible_wisdom.organizations.models import Organization


class TestOrganization(TestCase):
    def test_org_with_telemetry_schema_2_opted_in(self):
        organization = Organization.objects.get_or_create(id=123, _telemetry_opt_out=False)[0]
        self.assertFalse(organization.telemetry_opt_out)

    def test_org_with_telemetry_schema_2_opted_out(self):
        organization = Organization.objects.get_or_create(id=123, _telemetry_opt_out=True)[0]
        self.assertTrue(organization.telemetry_opt_out)

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @patch.object(feature_flags, 'LDClient')
    def test_org_with_telemetry_schema_2_opted_in_with_feature_flag_override(self, LDClient):
        LDClient.return_value.variation.return_value = True
        organization = Organization.objects.get_or_create(id=123, _telemetry_opt_out=True)[0]
        self.assertTrue(organization.telemetry_opt_out)

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @patch.object(feature_flags, 'LDClient')
    def test_org_with_telemetry_schema_2_opted_in_with_feature_flag_no_override(self, LDClient):
        LDClient.return_value.variation.return_value = False
        organization = Organization.objects.get_or_create(id=123, _telemetry_opt_out=True)[0]
        self.assertTrue(organization.telemetry_opt_out)

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @patch.object(feature_flags, 'LDClient')
    def test_org_with_telemetry_schema_2_opted_out_with_feature_flag_override(self, LDClient):
        LDClient.return_value.variation.return_value = True
        organization = Organization.objects.get_or_create(id=123, _telemetry_opt_out=False)[0]
        self.assertFalse(organization.telemetry_opt_out)

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @patch.object(feature_flags, 'LDClient')
    def test_org_with_telemetry_schema_2_opted_out_with_feature_flag_no_override(self, LDClient):
        LDClient.return_value.variation.return_value = False
        organization = Organization.objects.get_or_create(id=123, _telemetry_opt_out=False)[0]
        self.assertFalse(organization.telemetry_opt_out)

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @patch.object(feature_flags, 'LDClient')
    def test_org_with_unlimited_access_allowed_with_feature_flag_override(self, LDClient):
        LDClient.return_value.variation.return_value = True
        organization = Organization.objects.get_or_create(id=123, _telemetry_opt_out=False)[0]
        self.assertTrue(organization.is_subscription_check_should_be_bypassed)

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @patch.object(feature_flags, 'LDClient')
    def test_org_with_no_unlimited_access_allowed_with_feature_flag_no_override(self, LDClient):
        LDClient.return_value.variation.return_value = False
        organization = Organization.objects.get_or_create(id=123, _telemetry_opt_out=False)[0]
        self.assertFalse(organization.is_subscription_check_should_be_bypassed)
