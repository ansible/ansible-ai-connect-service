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

from datetime import datetime
from functools import wraps
from http import HTTPStatus
from unittest.mock import Mock, PropertyMock, patch

import requests
from django.test import TestCase, override_settings
from prometheus_client import Counter, Histogram
from requests.exceptions import HTTPError

from ansible_ai_connect.test_utils import WisdomServiceLogAwareTestCase
from ansible_ai_connect.users.authz_checker import (
    AMSCheck,
    DummyCheck,
    Token,
    authz_ams_get_metrics_hist,
    authz_ams_get_organization_hist,
    authz_ams_get_organization_quota_cost_hist,
    authz_ams_org_cache_hit_counter,
    authz_ams_rh_org_has_subscription_cache_hit_counter,
    authz_ams_service_retry_counter,
    authz_token_service_hist,
    authz_token_service_retry_counter,
    fatal_exception,
)


def assert_call_count_metrics(metric):
    def count_metrics_decorator(func):
        @wraps(func)
        def wrapped_function(*args, **kwargs):
            def get_count():
                for m in metric.collect():
                    for sample in m.samples:
                        if isinstance(metric, Histogram) and sample.name.endswith("_count"):
                            return sample.value
                        if isinstance(metric, Counter) and sample.name.endswith("_total"):
                            return sample.value
                return 0.0

            count_before = get_count()
            func(*args, **kwargs)
            count_after = get_count()
            assert count_after > count_before

        return wrapped_function

    return count_metrics_decorator


@override_settings(AUTHZ_AMS_SERVICE_RETRY_COUNT=1)
class TestToken(WisdomServiceLogAwareTestCase):
    def get_default_ams_checker(self):
        return AMSCheck("foo", "bar", "https://sso.redhat.com", "https://some-api.server.host")

    @patch("requests.post")
    def test_token_refresh(self, m_post):
        m_r = Mock()
        m_r.json.return_value = {"access_token": "foo_bar", "expires_in": 900}
        m_r.status_code = 200
        m_post.return_value = m_r

        my_token = Token("foo", "bar")
        my_token.refresh()
        self.assertGreater(my_token.expiration_date, datetime.utcnow())
        self.assertEqual(my_token.access_token, "foo_bar")

        # Ensure we serve the cached result the second time
        m_r.json.reset_mock()
        self.assertEqual(my_token.get(), "foo_bar")
        self.assertEqual(m_r.json.call_count, 0)

    @patch("requests.post")
    @assert_call_count_metrics(metric=authz_token_service_retry_counter)
    @assert_call_count_metrics(metric=authz_token_service_hist)
    @override_settings(AUTHZ_SSO_TOKEN_SERVICE_RETRY_COUNT=1)
    def test_token_refresh_with_500_status_code(self, m_post):
        m_post.side_effect = HTTPError(
            "Internal Server Error", response=Mock(status_code=500, text="Internal Server Error")
        )

        with self.assertLogs(logger="ansible_ai_connect.users.authz_checker", level="INFO") as log:
            my_token = Token("foo", "bar")
            self.assertIsNone(my_token.refresh())
            self.assertInLog("SSO token service failed", log)
            self.assertInLog("Caught retryable error after 1 tries.", log)

    @patch("requests.post")
    @assert_call_count_metrics(metric=authz_token_service_retry_counter)
    @assert_call_count_metrics(metric=authz_token_service_hist)
    @override_settings(AUTHZ_SSO_TOKEN_SERVICE_RETRY_COUNT=1)
    def test_token_refresh_success_on_retry(self, m_post):
        fail_side_effect = HTTPError(
            "Internal Server Error", response=Mock(status_code=500, text="Internal Server Error")
        )
        success_mock = Mock()
        success_mock.json.return_value = {"access_token": "foo_bar", "expires_in": 900}
        success_mock.status_code = 200

        m_post.side_effect = [fail_side_effect, success_mock]

        with self.assertLogs(logger="ansible_ai_connect.users.authz_checker", level="INFO") as log:
            my_token = Token("foo", "bar")
            my_token.refresh()
            self.assertGreater(my_token.expiration_date, datetime.utcnow())
            self.assertEqual(my_token.access_token, "foo_bar")
            self.assertInLog("Caught retryable error after 1 tries.", log)

    def test_fatal_exception(self):
        """Test the logic to determine if an exception is fatal or not"""
        exc = Exception()
        b = fatal_exception(exc)
        self.assertFalse(b)

        exc = requests.RequestException()
        response = requests.Response()
        response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
        exc.response = response
        b = fatal_exception(exc)
        self.assertFalse(b)

        exc = requests.RequestException()
        response = requests.Response()
        response.status_code = HTTPStatus.TOO_MANY_REQUESTS
        exc.response = response
        b = fatal_exception(exc)
        self.assertFalse(b)

        exc = requests.RequestException()
        response = requests.Response()
        response.status_code = HTTPStatus.BAD_REQUEST
        exc.response = response
        b = fatal_exception(exc)
        self.assertTrue(b)

    @assert_call_count_metrics(metric=authz_ams_org_cache_hit_counter)
    @assert_call_count_metrics(metric=authz_ams_get_organization_hist)
    def test_ams_get_ams_org(self):
        m_r = Mock()
        m_r.json.return_value = {"items": [{"id": "qwe"}]}
        m_r.status_code = 200

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.return_value = m_r
        self.assertEqual(checker.get_ams_org(123), "qwe")
        checker._session.get.assert_called_with(
            "https://some-api.server.host/api/accounts_mgmt/v1/organizations",
            params={"search": "external_id='123'"},
            timeout=3.0,
        )

        # Ensure the second call is cached
        m_r.json.reset_mock()
        self.assertEqual(checker.get_ams_org(123), "qwe")
        self.assertEqual(m_r.json.call_count, 0)

    def test_ams_get_ams_org_with_500_status_code(self):
        m_r = Mock()
        m_r.status_code = 500

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.return_value = m_r

        with self.assertLogs(logger="root", level="ERROR") as log:
            with self.assertRaises(AMSCheck.AMSError):
                checker.get_ams_org(123)
            self.assertInLog(
                "Unexpected error code (500) returned by AMS backend (organizations)", log
            )

    @assert_call_count_metrics(metric=authz_ams_service_retry_counter)
    def test_ams_get_ams_org_success_on_retry(self):
        fail_side_effect = HTTPError(
            "Internal Server Error", response=Mock(status_code=500, text="Internal Server Error")
        )
        success_mock = Mock()
        success_mock.json.return_value = {"items": [{"id": "qwe"}]}
        success_mock.status_code = 200

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.side_effect = [fail_side_effect, success_mock]

        with self.assertLogs(logger="ansible_ai_connect.users.authz_checker", level="INFO") as log:
            self.assertEqual(checker.get_ams_org(123), "qwe")
            self.assertInLog("Caught retryable error after 1 tries.", log)

    def test_ams_get_ams_org_with_empty_data(self):
        m_r = Mock()
        m_r.json.return_value = {"items": []}
        m_r.status_code = 200

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.return_value = m_r

        with self.assertLogs(logger="root", level="INFO") as log:
            self.assertEqual(checker.get_ams_org(123), AMSCheck.ERROR_AMS_ORG_UNDEFINED)
            self.assertInLog(
                "An AMS Organization could not be found. " "rh_org_id: 123.",
                log,
            )

    @assert_call_count_metrics(metric=authz_ams_get_metrics_hist)
    def test_ams_self_test_success(self):
        m_r = Mock()
        m_r.status_code = 200

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.return_value = m_r
        try:
            checker.self_test()
        except HTTPError:
            self.fail("self_test() should not have raised an exception.")

    @assert_call_count_metrics(metric=authz_ams_get_metrics_hist)
    def test_ams_self_test_failure(self):
        r = requests.models.Response()
        r.status_code = 500

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.return_value = r

        with self.assertRaises(HTTPError):
            checker.self_test()

    def test_rh_user_is_org_admin(self):
        m_r = Mock()
        m_r.json.side_effect = [
            {"items": [{"id": "123"}]},
            {"items": [{"role": {"id": "OrganizationAdmin"}}]},
        ]
        m_r.status_code = 200

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.return_value = m_r

        self.assertTrue(checker.rh_user_is_org_admin("user", 123))
        checker._session.get.assert_called_with(
            "https://some-api.server.host/api/accounts_mgmt/v1/role_bindings",
            params={"search": "account.username = 'user' AND organization.id='123'"},
            timeout=3.0,
        )

    def test_rh_user_is_org_admin_when_ams_fails(self):
        m_r = Mock()
        m_r.status_code = 500

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.return_value = m_r

        self.assertFalse(checker.rh_user_is_org_admin("user", 123))

    def test_rh_user_is_org_admin_when_get_ams_org_returns_empty_response(self):
        m_r = Mock()
        m_r.json.side_effect = [
            # Invocation 1
            # AMS get_ams_org() response
            {"items": []},
            # Invocation 2
            # AMS get_ams_org() response
            {"items": []},
        ]
        m_r.status_code = 200

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.return_value = m_r

        self.assertFalse(checker.rh_user_is_org_admin("user", 123))
        self.assertEqual(m_r.json.call_count, 1)

        # Ensure the second call is not cached
        m_r.json.reset_mock()
        self.assertFalse(checker.rh_user_is_org_admin("user", 123))
        self.assertEqual(m_r.json.call_count, 1)

    def test_is_not_org_admin(self):
        m_r = Mock()
        m_r.json.side_effect = [
            {"items": [{"id": "123"}]},
            {"items": [{"role": {"id": "NotAnAdmin"}}]},
        ]
        m_r.status_code = 200

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.return_value = m_r

        self.assertFalse(checker.rh_user_is_org_admin("user", 123))
        checker._session.get.assert_called_with(
            "https://some-api.server.host/api/accounts_mgmt/v1/role_bindings",
            params={"search": "account.username = 'user' AND organization.id='123'"},
            timeout=3.0,
        )

    def test_user_has_no_role(self):
        m_r = Mock()
        m_r.json.side_effect = [
            {"items": [{"id": "123"}]},
            {"items": [{"role": {}}]},
        ]
        m_r.status_code = 200
        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.return_value = m_r

        self.assertFalse(checker.rh_user_is_org_admin("user", 123))

    def test_role_has_no_id(self):
        m_r = Mock()
        m_r.json.side_effect = [
            {"items": [{"id": "123"}]},
            {"items": []},
        ]
        m_r.status_code = 200
        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.return_value = m_r

        self.assertFalse(checker.rh_user_is_org_admin("user", 123))

    def test_rh_user_is_org_admin_timeout(self):
        def side_effect(*args, **kwargs):
            raise requests.exceptions.Timeout()

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.side_effect = side_effect
        with self.assertLogs(logger="root", level="ERROR") as log:
            self.assertFalse(checker.rh_user_is_org_admin("user", 123))
            self.assertInLog(AMSCheck.ERROR_AMS_CONNECTION_TIMEOUT, log)

    def test_rh_user_is_org_admin_network_error(self):
        m_r = Mock()
        m_r.status_code = 500

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.return_value = m_r

        with self.assertLogs(logger="root", level="ERROR") as log:
            self.assertFalse(checker.rh_user_is_org_admin("user", 123))
            self.assertInLog(
                "Unexpected error code (500) returned by AMS backend (organizations).",
                log,
            )

    @assert_call_count_metrics(metric=authz_ams_rh_org_has_subscription_cache_hit_counter)
    @assert_call_count_metrics(metric=authz_ams_get_organization_quota_cost_hist)
    def test_rh_org_has_subscription(self):
        m_r = Mock()
        m_r.json.side_effect = [
            {"items": [{"id": "rdgdfhbrdb"}]},
            {"items": [{"allowed": 10}], "total": 1},
        ]
        m_r.status_code = 200

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.return_value = m_r

        self.assertTrue(checker.rh_org_has_subscription(123))
        checker._session.get.assert_called_with(
            (
                "https://some-api.server.host"
                "/api/accounts_mgmt/v1/organizations/rdgdfhbrdb/quota_cost"
            ),
            params={"search": "quota_id LIKE 'seat|ansible.wisdom%'"},
            timeout=3.0,
        )

        # Ensure the second call is cached
        m_r.json.reset_mock()
        self.assertTrue(checker.rh_org_has_subscription(123))
        self.assertEqual(m_r.json.call_count, 0)

    @assert_call_count_metrics(metric=authz_ams_service_retry_counter)
    @assert_call_count_metrics(metric=authz_ams_get_organization_quota_cost_hist)
    def test_rh_org_has_subscription_success_on_retry(self):
        fail_side_effect = HTTPError(
            "Internal Server Error", response=Mock(status_code=500, text="Internal Server Error")
        )
        success_mock = Mock()
        success_mock.json.return_value = {"items": [{"allowed": 10}], "total": 1}
        success_mock.status_code = 200

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.side_effect = [fail_side_effect, success_mock]
        checker.get_ams_org = Mock(return_value="abc")

        with self.assertLogs(logger="ansible_ai_connect.users.authz_checker", level="INFO") as log:
            self.assertTrue(checker.rh_org_has_subscription(123))
            self.assertInLog("Caught retryable error after 1 tries.", log)

    def test_rh_org_has_subscription_when_ams_fails(self):
        m_r = Mock()
        m_r.status_code = 500

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.return_value = m_r

        self.assertTrue(checker.rh_org_has_subscription(123))

    def test_rh_org_has_subscription_when_get_ams_org_returns_empty_response(self):
        m_r = Mock()
        m_r.json.side_effect = [
            # Invocation 1
            # AMS get_ams_org() response
            {"items": []},
            # Invocation 2
            # AMS get_ams_org() response
            {"items": []},
        ]
        m_r.status_code = 200

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.return_value = m_r

        self.assertFalse(checker.rh_org_has_subscription(123))
        self.assertEqual(m_r.json.call_count, 1)

        # Ensure the second call is not cached
        m_r.json.reset_mock()
        self.assertFalse(checker.rh_org_has_subscription(123))
        self.assertEqual(m_r.json.call_count, 1)

    def test_is_org_not_lightspeed_subscriber(self):
        m_r = Mock()
        m_r.json.side_effect = [
            {"items": [{"id": "rdgdfhbrdb"}]},
            {"items": [], "total": 0},
        ]
        m_r.status_code = 200

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.return_value = m_r

        self.assertFalse(checker.rh_org_has_subscription(123))
        checker._session.get.assert_called_with(
            (
                "https://some-api.server.host"
                "/api/accounts_mgmt/v1/organizations/rdgdfhbrdb/quota_cost"
            ),
            params={"search": "quota_id LIKE 'seat|ansible.wisdom%'"},
            timeout=3.0,
        )

    def test_rh_org_has_subscription_timeout(self):
        def side_effect(*args, **kwargs):
            raise requests.exceptions.Timeout()

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.side_effect = side_effect
        checker.get_ams_org = Mock(return_value="abc")

        with self.assertLogs(logger="root", level="ERROR") as log:
            self.assertFalse(checker.rh_org_has_subscription(123))
            self.assertInLog(AMSCheck.ERROR_AMS_CONNECTION_TIMEOUT, log)

    def test_rh_org_has_subscription_network_error(self):
        m_r = Mock()
        p = PropertyMock(return_value=500)
        type(m_r).status_code = p

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.return_value = m_r
        checker.get_ams_org = Mock(return_value="abc")

        with self.assertLogs(logger="root", level="ERROR") as log:
            self.assertFalse(checker.rh_org_has_subscription(123))
            self.assertInLog(
                "Unexpected error code (500) returned by AMS backend (quota_cost).",
                log,
            )
            p.assert_called()
            # Ensure the second call is NOT cached
            p.reset_mock()
            self.assertFalse(checker.rh_org_has_subscription(123))
            p.assert_called()

    def test_rh_org_has_subscription_wrong_output(self):
        m_r = Mock()
        m_r.json.side_effect = [
            {"items": [{"id": "rdgdfhbrdb"}]},
            {"msg": "something unexpected"},
        ]
        m_r.status_code = 200

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.return_value = m_r

        with self.assertLogs(logger="root", level="ERROR") as log:
            self.assertFalse(checker.rh_org_has_subscription(123))
            self.assertInLog("Unexpected answer from AMS backend (quota_cost).", log)

    def test_get_organization(self):
        m_r = Mock()
        m_r.json.side_effect = [
            {"items": [{"external_id": "123"}]},
        ]
        m_r.status_code = 200

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.return_value = m_r

        self.assertEqual(checker.get_organization(123)["external_id"], "123")
        checker._session.get.assert_called_once_with(
            "https://some-api.server.host/api/accounts_mgmt/v1/organizations",
            params={"search": "external_id='123'"},
            timeout=3.0,
        )


class TestDummy(TestCase):
    def setUp(self):
        super().setUp()
        self.checker = DummyCheck()

    def test_self_test(self):
        self.assertIsNone(self.checker.self_test())

    @override_settings(AUTHZ_DUMMY_ORGS_WITH_SUBSCRIPTION="123")
    def test_rh_org_has_subscription_with_sub(self):
        self.assertTrue(self.checker.rh_org_has_subscription(123))

    @override_settings(AUTHZ_DUMMY_ORGS_WITH_SUBSCRIPTION="123")
    def test_rh_org_has_subscription_with_param_as_string(self):
        self.assertFalse(self.checker.rh_org_has_subscription("123"))

    @override_settings(AUTHZ_DUMMY_ORGS_WITH_SUBSCRIPTION="")
    def test_rh_org_has_subscription_no_sub(self):
        self.assertFalse(self.checker.rh_org_has_subscription(13))

    @override_settings(AUTHZ_DUMMY_ORGS_WITH_SUBSCRIPTION="*")
    def test_rh_org_has_subscription_all(self):
        self.assertTrue(self.checker.rh_org_has_subscription(56))

    def test_get_organization(self):
        self.assertEqual(self.checker.get_organization(56)["external_id"], "56")
