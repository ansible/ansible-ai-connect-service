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

from http import HTTPStatus
from unittest.mock import patch

from django.test import override_settings
from django.urls import resolve, reverse
from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
from rest_framework.permissions import IsAuthenticated

import ansible_ai_connect.ai.feature_flags as feature_flags
from ansible_ai_connect.ai.api.permissions import (
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
)
from ansible_ai_connect.organizations.models import ExternalOrganization
from ansible_ai_connect.test_utils import WisdomServiceAPITestCaseBaseOIDC


class TestConsoleView(WisdomServiceAPITestCaseBaseOIDC):
    def setUp(self):
        super().setUp()
        feature_flags.FeatureFlags.instance = None

    def test_authentication_error(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse("console"))
        self.assertEqual(r.status_code, HTTPStatus.FOUND)
        self.assertEqual(r.url, "/login?next=/console/")

    @patch.object(IsOrganisationAdministrator, "has_permission", return_value=True)
    @patch.object(IsOrganisationLightspeedSubscriber, "has_permission", return_value=True)
    def test_get_when_authenticated(self, *args):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse("console"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertEqual(r.template_name, ["console/console.html"])

    # Mock IsOrganisationAdministrator Permission not being satisfied
    @patch.object(IsOrganisationAdministrator, "has_permission", return_value=False)
    @patch.object(IsOrganisationLightspeedSubscriber, "has_permission", return_value=True)
    def test_get_when_authenticated_missing_permission_administrator(self, *args):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse("console"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertEqual(r.template_name, ["console/denied.html"])

    # Mock IsOrganisationLightspeedSubscriber Permission not being satisfied
    @patch.object(IsOrganisationAdministrator, "has_permission", return_value=True)
    @patch.object(IsOrganisationLightspeedSubscriber, "has_permission", return_value=False)
    def test_get_when_authenticated_missing_permission_subscription(self, *args):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse("console"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertEqual(r.template_name, ["console/denied.html"])

    def test_permission_classes(self, *args):
        url = reverse("console")
        view = resolve(url).func.view_class

        required_permissions = [
            IsAuthenticated,
            IsAuthenticatedOrTokenHasScope,
        ]
        self.assertEqual(len(view.permission_classes), len(required_permissions))
        for permission in required_permissions:
            self.assertTrue(permission in view.permission_classes)

    @patch.object(IsOrganisationAdministrator, "has_permission", return_value=True)
    @patch.object(IsOrganisationLightspeedSubscriber, "has_permission", return_value=True)
    def test_extra_data(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("console"))
        self.assertIsInstance(response.context_data, dict)
        context = response.context_data
        self.assertEqual(context["user_name"], self.user.username)
        self.assertEqual(context["rh_org_has_subscription"], self.user.rh_org_has_subscription)

    @override_settings(LAUNCHDARKLY_SDK_KEY="dummy_key")
    @patch.object(feature_flags, "LDClient")
    def test_extra_data_telemetry_feature(self, LDClient, *args):
        LDClient.return_value.variation.return_value = True
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("console"))
        self.assertIsInstance(response.context_data, dict)
        context = response.context_data
        self.assertEqual(
            context["telemetry_schema_2_admin_dashboard_url"],
            "https://console.stage.redhat.com/ansible/lightspeed-admin-dashboard",
        )
