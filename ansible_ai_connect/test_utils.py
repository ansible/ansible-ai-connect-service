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

import logging
import random
import string
from ast import literal_eval
from datetime import datetime
from datetime import timezone as dt_timezone
from http import HTTPStatus
from typing import Optional, Union
from unittest.mock import patch
from uuid import uuid4

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITransactionTestCase
from segment import analytics
from social_django.models import UserSocialAuth

from ansible_ai_connect.ai.api.utils import segment_analytics_telemetry
from ansible_ai_connect.ai.api.utils.version import api_version_reverse
from ansible_ai_connect.organizations.models import Organization
from ansible_ai_connect.users.constants import USER_SOCIAL_AUTH_PROVIDER_OIDC
from ansible_ai_connect.users.models import Plan

logger = logging.getLogger(__name__)


def create_user(
    provider: str = None,
    social_auth_extra_data: any = {},
    rh_user_is_org_admin: Optional[bool] = None,
    rh_org_has_subscription: Optional[bool] = None,
    rh_user_id: str = None,
    rh_org_id: int = 1234567,
    org_opt_out: bool = False,
    **kwargs,
):
    (org, _) = Organization.objects.get_or_create(id=rh_org_id, telemetry_opt_out=org_opt_out)
    kwargs.setdefault("username", "u" + "".join(random.choices(string.digits, k=5)))
    kwargs.setdefault("password", "secret")
    kwargs.setdefault("email", kwargs["username"] + "@example.com")
    user = get_user_model().objects.create_user(
        organization=org if provider == USER_SOCIAL_AUTH_PROVIDER_OIDC else None,
        **kwargs,
    )
    if provider:
        rh_user_id = rh_user_id or str(uuid4())
        user.external_username = kwargs.get("external_username") or kwargs.get("username")
        social_auth = UserSocialAuth.objects.create(user=user, provider=provider, uid=rh_user_id)
        social_auth.set_extra_data(social_auth_extra_data)
        if rh_user_is_org_admin:
            user.rh_user_is_org_admin = rh_user_is_org_admin
        if rh_org_has_subscription:
            user.rh_org_has_subscription = rh_org_has_subscription
    user.save()
    return user


def create_user_with_provider(**kwargs):
    kwargs.setdefault("username", "test_user_name")
    kwargs.setdefault("password", "test_passwords")
    kwargs.setdefault("provider", USER_SOCIAL_AUTH_PROVIDER_OIDC)
    kwargs.setdefault("external_username", "anexternalusername")
    return create_user(
        **kwargs,
    )


class WisdomLogAwareMixin:
    @staticmethod
    def searchInLogOutput(s, logs, number_of_matches_expected=None):
        found_cpt = sum(o.count(s) for o in logs.output)
        return (
            found_cpt == number_of_matches_expected
            if number_of_matches_expected
            else bool(found_cpt)
        )

    @staticmethod
    def extractSegmentEventsFromLog(logs):
        events = []
        for log in logs.output:
            if log.startswith("DEBUG:segment:queueing: "):
                obj = literal_eval(
                    log.replace("DEBUG:segment:queueing: ", "")
                    .replace("\n", "")
                    .replace("DataSource.UNKNOWN", "0")
                    .replace("AnsibleType.UNKNOWN", "0")
                )
                events.append(obj)
        return events


class WisdomTestCase(TestCase):

    def setUp(self):
        super().setUp()
        # Ensure the Model Pipeline factory cache is clear
        apps.get_app_config("ai").ready()

    def assert_error_detail(self, r, code: str, message: str = None):
        if r.status_code == HTTPStatus.NO_CONTENT:
            self.assertIsNone(r.data)
            self.assertEqual(r["Content-Length"], "0")
            return

        r_code = r.data.get("code")
        self.assertEqual(r_code, code)
        if message:
            r_message = r.data.get("message")
            self.assertEqual(r_message, message)


class WisdomServiceLogAwareTestCase(WisdomTestCase, WisdomLogAwareMixin):
    def assertInLog(self, s, logs, number_of_matches_expected=None):
        self.assertTrue(self.searchInLogOutput(s, logs, number_of_matches_expected), logs)

    def assertNotInLog(self, s, logs):
        self.assertFalse(self.searchInLogOutput(s, logs), logs)

    def assertSegmentTimestamp(self, log):
        segment_events = self.extractSegmentEventsFromLog(log)
        for event in segment_events:
            self.assertIsNotNone(event["timestamp"])

    def assert_segment_log(self, log, event: str, problem: Union[str, None], **kwargs):
        segment_events = self.extractSegmentEventsFromLog(log)
        self.assertTrue(len(segment_events) == 1)
        self.assertEqual(segment_events[0]["event"], event)
        if problem:
            self.assertEqual(segment_events[0]["properties"]["problem"], problem)
            self.assertEqual(
                segment_events[0]["properties"]["exception"], True if problem else False
            )
        for key, value in kwargs.items():
            self.assertEqual(segment_events[0]["properties"][key], value)


class WisdomAppsBackendMocking(WisdomTestCase):
    """
    Ensure that the apps backend are properly reinitialized between each tests and avoid
    potential side-effects.
    """

    def setUp(self):
        super().setUp()
        self.backend_patchers = {
            key: patch.object(apps.get_app_config("ai"), key, None)
            for key in [
                "_ansible_lint_caller",
                "_seat_checker",
                "_wca_secret_manager",
            ]
        }
        for key, mocker in self.backend_patchers.items():
            mocker.start()

    def tearDown(self):
        for patcher in self.backend_patchers.values():
            patcher.stop()
        super().tearDown()

    @staticmethod
    def mock_ansible_lint_caller_with(mocked):
        apps.get_app_config("ai")._ansible_lint_caller = mocked

    @staticmethod
    def mock_seat_checker_with(mocked):
        apps.get_app_config("ai")._seat_checker = mocked

    @staticmethod
    def mock_wca_secret_manager_with(mocked):
        apps.get_app_config("ai")._wca_secret_manager = mocked

    @staticmethod
    def mock_reports_postman_with(mocked):
        apps.get_app_config("ai")._reports_postman = mocked


class WisdomServiceAPITestCaseBase(APITransactionTestCase, WisdomServiceLogAwareTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        analytics.send = False  # do not send data to segment from unit tests
        segment_analytics_telemetry.send = False  # do not send data to segment from unit tests

    def create_user(self):
        logger.warn("Please move this test to WisdomServiceAPITestCaseBaseOIDC")

        self.user = get_user_model().objects.create_user(
            username=self.username,
            email=self.email,
            password=self.password,
        )

    def setUp(self):
        super().setUp()
        self.username = "u" + "".join(random.choices(string.digits, k=5))
        self.password = "secret"
        self.email = "user@example.com"
        self.create_user()

        self.user.user_id = str(uuid4())
        self.user.community_terms_accepted = timezone.now()
        self.user.save()

        group_1, _ = Group.objects.get_or_create(name="Group 1")
        group_2, _ = Group.objects.get_or_create(name="Group 2")
        group_1.user_set.add(self.user)
        group_2.user_set.add(self.user)
        cache.clear()

    def tearDown(self):
        Organization.objects.filter(id=1).delete()
        self.user.delete()
        super().tearDown()

    def login(self):
        self.client.login(username=self.username, password=self.password)


class WisdomServiceAPITestCaseBaseOIDC(WisdomServiceAPITestCaseBase):
    """This class should ultimately replace WisdomServiceAPITestCaseBase"""

    api_version: str = "v0"

    @classmethod
    def api_version_reverse(cls, view_name, **kwargs):
        return api_version_reverse(view_name, api_version=cls.api_version, **kwargs)

    def create_user(self):
        self.user = create_user_with_provider(
            username=self.username,
            email=self.email,
            password=self.password,
            provider=USER_SOCIAL_AUTH_PROVIDER_OIDC,
            rh_org_id=1981,
            social_auth_extra_data={},
        )

    def start_user_plan(self):
        self.trial_plan, _ = Plan.objects.get_or_create(name="Some plan", expires_after="10 days")
        self.trial_plan.created_at = datetime(2000, 1, 1, tzinfo=dt_timezone.utc)
        self.user.plans.add(self.trial_plan)


class APIVersionTestCaseBase:
    api_version: str = "v0"

    @classmethod
    def api_version_reverse(cls, view_name, **kwargs):
        return api_version_reverse(view_name, api_version=cls.api_version, **kwargs)
