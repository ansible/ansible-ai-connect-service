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
import unittest
from io import StringIO
from unittest.mock import Mock

from dateutil.relativedelta import relativedelta
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.utils import timezone

from ansible_ai_connect.test_utils import (
    WisdomAppsBackendMocking,
    WisdomServiceLogAwareTestCase,
    WisdomTestCase,
)
from ansible_ai_connect.users.constants import TRIAL_PLAN_NAME
from ansible_ai_connect.users.models import Plan


@override_settings(ANSIBLE_AI_ONE_CLICK_REPORTS_POSTMAN="none")
class TestGenerateUsersTrialsReports(WisdomAppsBackendMocking, WisdomServiceLogAwareTestCase):

    def setUp(self):
        super().setUp()
        self.postman = Mock()
        self.postman.send_reports = Mock()
        self.mock_reports_postman_with(self.postman)
        self.trial_plan, _ = Plan.objects.get_or_create(
            name=TRIAL_PLAN_NAME, expires_after="90 days"
        )

    @staticmethod
    def call_command(*args, **kwargs):
        out = StringIO()
        call_command(
            "generate_users_trials_reports",
            *args,
            stdout=out,
            stderr=StringIO(),
            **kwargs,
        )
        return out.getvalue()

    def test_dry_run(self):
        with self.assertLogs(logger="root", level="INFO") as log:
            out = TestGenerateUsersTrialsReports.call_command("--dry-run")
            self.assertInLog("First name,Last name,Organization name,Plan name,Trial started", log)
            self.assertInLog("First name,Last name,Email,Plan name,Trial started", log)
            self.assertIn("Reports not sent", out)

    def test_auto_date_range(self):
        before = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        after = before - relativedelta(days=1)
        TestGenerateUsersTrialsReports.call_command("--auto-range")

        reports = self.postman.send_reports.call_args.args[0]
        self.assertEqual(reports.plan_id, self.trial_plan.id)
        self.assertEqual(reports.created_before, before)
        self.assertEqual(reports.created_after, after)

    def test_empty(self):
        TestGenerateUsersTrialsReports.call_command()

        reports = self.postman.send_reports.call_args.args[0]
        self.assertEqual(reports.plan_id, self.trial_plan.id)
        self.assertIsNone(reports.created_after)
        self.assertIsNone(reports.created_before)

    def test_plan_id(self):
        TestGenerateUsersTrialsReports.call_command(plan_id=self.trial_plan.id)

        reports = self.postman.send_reports.call_args.args[0]
        self.assertEqual(reports.plan_id, self.trial_plan.id)
        self.assertIsNone(reports.created_after)
        self.assertIsNone(reports.created_before)

    def test_invalid_plan_id(self):
        with self.assertRaises(Plan.DoesNotExist):
            TestGenerateUsersTrialsReports.call_command(plan_id=999999)

    def test_created_before(self):
        now = timezone.now()
        TestGenerateUsersTrialsReports.call_command(created_before=now)

        reports = self.postman.send_reports.call_args.args[0]
        self.assertEqual(reports.plan_id, self.trial_plan.id)
        self.assertIsNone(reports.created_after)
        self.assertEqual(reports.created_before, now)

    def test_created_after(self):
        now = timezone.now()
        TestGenerateUsersTrialsReports.call_command(created_after=now)

        reports = self.postman.send_reports.call_args.args[0]
        self.assertEqual(reports.plan_id, self.trial_plan.id)
        self.assertEqual(reports.created_after, now)
        self.assertIsNone(reports.created_before)

    def test_plan_id_invalid_value(self):
        with self.assertRaises(ValueError):
            TestGenerateUsersTrialsReports.call_command(plan_id="banana")

    def test_created_before_invalid_value(self):
        with self.assertRaises(ValidationError):
            TestGenerateUsersTrialsReports.call_command(created_before="banana")

    def test_created_after_invalid_value(self):
        with self.assertRaises(ValidationError):
            TestGenerateUsersTrialsReports.call_command(created_after="banana")

    def test_error_handling(self):
        self.postman.send_reports = Mock(side_effect=Exception("Something horrible happened"))
        with self.assertRaises(CommandError):
            out = TestGenerateUsersTrialsReports.call_command()
            self.assertIn("Something horrible happened", out)


@unittest.skip("Used for debugging slack-webhook functionality")
@override_settings(ANSIBLE_AI_ONE_CLICK_REPORTS_POSTMAN="slack-webhook")
class TestGenerateUsersTrialsReportsSlackWebhook(WisdomTestCase):

    @staticmethod
    def call_command(*args, **kwargs):
        out = StringIO()
        call_command(
            "generate_users_trials_reports",
            *args,
            stdout=out,
            stderr=StringIO(),
            **kwargs,
        )
        return out.getvalue()

    def test_empty(self):
        TestGenerateUsersTrialsReports.call_command()


@unittest.skip("Used for debugging slack-webapi functionality")
@override_settings(ANSIBLE_AI_ONE_CLICK_REPORTS_POSTMAN="slack-webapi")
class TestGenerateUsersTrialsReportsSlackWebApi(WisdomTestCase):

    @staticmethod
    def call_command(*args, **kwargs):
        out = StringIO()
        call_command(
            "generate_users_trials_reports",
            *args,
            stdout=out,
            stderr=StringIO(),
            **kwargs,
        )
        return out.getvalue()

    def test_empty(self):
        TestGenerateUsersTrialsReports.call_command()


@unittest.skip("Used for debugging google-drive functionality")
@override_settings(ANSIBLE_AI_ONE_CLICK_REPORTS_POSTMAN="google-drive")
class TestGenerateUsersTrialsReportsGoogleDrive(WisdomTestCase):

    @staticmethod
    def call_command(*args, **kwargs):
        out = StringIO()
        call_command(
            "generate_users_trials_reports",
            *args,
            stdout=out,
            stderr=StringIO(),
            **kwargs,
        )
        return out.getvalue()

    def test_empty(self):
        TestGenerateUsersTrialsReports.call_command()
