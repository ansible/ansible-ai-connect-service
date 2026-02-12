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

from ansible_ai_connect.organizations.models import ExternalOrganization
from ansible_ai_connect.test_utils import WisdomServiceAPITestCaseBaseOIDC


def get_feature_flags_that_say_False():
    class DummyFeatureFlags:
        def check_flag(self, flag=None, query_dict=None):
            return False

    return DummyFeatureFlags()


def get_feature_flags_that_say_True():
    class DummyFeatureFlags:
        def check_flag(self, flag=None, query_dict=None):
            return True

    return DummyFeatureFlags()


class TestOrganization(TestCase):
    def test_org_with_telemetry_schema_2_opted_in(self):
        organization = ExternalOrganization.objects.get_or_create(id=123, telemetry_opt_out=False)[
            0
        ]
        self.assertFalse(organization.has_telemetry_opt_out)

    def test_org_with_telemetry_schema_2_opted_out(self):
        organization = ExternalOrganization.objects.get_or_create(id=123, telemetry_opt_out=True)[0]
        self.assertTrue(organization.has_telemetry_opt_out)

    @override_settings(LAUNCHDARKLY_SDK_KEY="dummy_key")
    @patch(
        "ansible_ai_connect.organizations.models.get_feature_flags", get_feature_flags_that_say_True
    )
    def test_org_with_telemetry_schema_2_opted_in_with_feature_flag_override(self):
        organization = ExternalOrganization.objects.get_or_create(id=123, telemetry_opt_out=True)[0]
        self.assertTrue(organization.has_telemetry_opt_out)

    @override_settings(LAUNCHDARKLY_SDK_KEY="dummy_key")
    @patch(
        "ansible_ai_connect.organizations.models.get_feature_flags",
        get_feature_flags_that_say_False,
    )
    def test_org_with_telemetry_schema_2_opted_in_with_feature_flag_no_override(self):
        organization = ExternalOrganization.objects.get_or_create(id=123, telemetry_opt_out=True)[0]
        self.assertTrue(organization.has_telemetry_opt_out)

    @override_settings(LAUNCHDARKLY_SDK_KEY="dummy_key")
    @patch(
        "ansible_ai_connect.organizations.models.get_feature_flags", get_feature_flags_that_say_True
    )
    def test_org_with_telemetry_schema_2_opted_out_with_feature_flag_override(self):
        organization = ExternalOrganization.objects.get_or_create(id=123, telemetry_opt_out=False)[
            0
        ]
        self.assertFalse(organization.has_telemetry_opt_out)

    @override_settings(LAUNCHDARKLY_SDK_KEY="dummy_key")
    @patch(
        "ansible_ai_connect.organizations.models.get_feature_flags",
        get_feature_flags_that_say_False,
    )
    def test_org_with_telemetry_schema_2_opted_out_with_feature_flag_no_override(self):
        organization = ExternalOrganization.objects.get_or_create(id=123, telemetry_opt_out=False)[
            0
        ]
        self.assertFalse(organization.has_telemetry_opt_out)

    @override_settings(LAUNCHDARKLY_SDK_KEY="dummy_key")
    @patch(
        "ansible_ai_connect.organizations.models.get_feature_flags", get_feature_flags_that_say_True
    )
    def test_org_with_unlimited_access_allowed_with_feature_flag_override(self):
        organization = ExternalOrganization.objects.get_or_create(id=123, telemetry_opt_out=False)[
            0
        ]
        self.assertTrue(organization.is_subscription_check_should_be_bypassed)

    @override_settings(LAUNCHDARKLY_SDK_KEY="dummy_key")
    @patch(
        "ansible_ai_connect.organizations.models.get_feature_flags",
        get_feature_flags_that_say_False,
    )
    def test_org_with_no_unlimited_access_allowed_with_feature_flag_no_override(self):
        organization = ExternalOrganization.objects.get_or_create(id=123, telemetry_opt_out=False)[
            0
        ]
        self.assertFalse(organization.is_subscription_check_should_be_bypassed)


@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
class TestOrganizationAPIKey(WisdomServiceAPITestCaseBaseOIDC):
    @override_settings(WCA_SECRET_DUMMY_SECRETS="1981:valid")
    def test_org_has_api_key(self):
        organization = ExternalOrganization.objects.get_or_create(id=1981, telemetry_opt_out=False)[
            0
        ]
        self.assertTrue(organization.has_api_key)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="")
    def test_org_does_not_have_api_key(self):
        organization = ExternalOrganization.objects.get_or_create(id=1981, telemetry_opt_out=False)[
            0
        ]
        self.assertFalse(organization.has_api_key)
