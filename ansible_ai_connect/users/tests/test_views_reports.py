#!/usr/bin/env python3

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

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import Group, Permission
from django.test import Client, override_settings
from django.urls import reverse

from ansible_ai_connect.test_utils import WisdomServiceAPITestCaseBaseOIDC
from ansible_ai_connect.users.models import Plan


class BaseReportViewTest:

    def initialise(self, test: WisdomServiceAPITestCaseBaseOIDC):
        self.test = test
        self.client = Client()
        self.client.force_login(test.user)
        self.group, _ = Group.objects.get_or_create(name="wisdom_view_users")
        for i in ["view_user", "view_userplan", "view_organization"]:
            self.group.permissions.add(Permission.objects.get(codename=i))

        self.trial_plan, _ = Plan.objects.get_or_create(
            name="Trial of 10 days", expires_after="10 days"
        )

    def get_report_header(self) -> str:
        pass

    def get_report_url_alias(self) -> str:
        pass

    def add_plan_to_user(self):
        self.test.user.plans.add(self.trial_plan)

    def test_get_report_with_no_permission(self):
        r = self.client.get(reverse(self.get_report_url_alias()))
        self.test.assertEqual(r.status_code, 403)
        self.test.assertEqual(r.accepted_media_type, "application/json")

    def test_get_report_response(self):
        self.test.user.groups.add(self.group)
        r = self.client.get(reverse(self.get_report_url_alias()))
        self.test.assertEqual(r.status_code, 200)
        self.test.assertEqual(r.accepted_media_type, "text/csv")
        self.test.assertTrue(self.get_report_header() in str(r.content))

    def test_get_report_with_no_plans(self):
        self.test.user.groups.add(self.group)
        r = self.client.get(reverse(self.get_report_url_alias()))
        self.test.assertTrue(self.get_report_header() in str(r.content))
        self.test.assertFalse("Trial of 10 days" in str(r.content))

    def test_get_report_with_plans(self):
        self.test.user.groups.add(self.group)
        self.add_plan_to_user()
        r = self.client.get(reverse(self.get_report_url_alias()))
        self.test.assertTrue(self.get_report_header() in str(r.content))
        self.test.assertTrue("Trial of 10 days" in str(r.content))

    def test_get_report_filter_by_existing_plan_id(self):
        self.test.user.groups.add(self.group)
        self.add_plan_to_user()
        r = self.client.get(
            reverse(self.get_report_url_alias()) + "?plan_id=" + str(self.trial_plan.id)
        )
        self.test.assertTrue(self.get_report_header() in str(r.content))
        self.test.assertTrue("Trial of 10 days" in str(r.content))

    def test_get_report_filter_by_non_existing_plan_id(self):
        self.test.user.groups.add(self.group)
        self.add_plan_to_user()
        r = self.client.get(reverse(self.get_report_url_alias()) + "?plan_id=999")
        self.test.assertTrue(self.get_report_header() in str(r.content))
        self.test.assertFalse("Trial of 10 days" in str(r.content))

    def test_get_report_filter_by_created_after(self):
        self.test.user.groups.add(self.group)
        self.add_plan_to_user()
        r = self.client.get(
            reverse(self.get_report_url_alias())
            + "?created_after="
            + (self.trial_plan.created_at + relativedelta(days=-1)).strftime("%Y-%m-%d")
        )
        self.test.assertTrue(self.get_report_header() in str(r.content))
        self.test.assertTrue("Trial of 10 days" in str(r.content))

    def test_get_report_filter_by_created_before(self):
        self.test.user.groups.add(self.group)
        self.add_plan_to_user()
        r = self.client.get(
            reverse(self.get_report_url_alias())
            + "?created_before="
            + (self.trial_plan.created_at + relativedelta(days=1)).strftime("%Y-%m-%d")
        )
        self.test.assertTrue(self.get_report_header() in str(r.content))
        self.test.assertTrue("Trial of 10 days" in str(r.content))


@override_settings(AUTHZ_BACKEND_TYPE="dummy")
class TestUserTrialsReportView(WisdomServiceAPITestCaseBaseOIDC, BaseReportViewTest):

    def setUp(self):
        super().setUp()
        super().initialise(self)

    def get_report_header(self) -> str:
        return "First name,Last name,Organization name,Plan name,Trial started"

    def get_report_url_alias(self) -> str:
        return "user_trials"


@override_settings(AUTHZ_BACKEND_TYPE="dummy")
class TestUserMarketingReportView(WisdomServiceAPITestCaseBaseOIDC, BaseReportViewTest):

    def setUp(self):
        super().setUp()
        super().initialise(self)

    def get_report_header(self) -> str:
        return "First name,Last name,Email,Plan name,Trial started"

    def get_report_url_alias(self) -> str:
        return "user_marketing"

    def add_plan_to_user(self):
        super().add_plan_to_user()
        up = self.user.userplan_set.first()
        up.accept_marketing = True
        up.save()
