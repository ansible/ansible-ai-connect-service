#!/usr/bin/env python3

from datetime import datetime
from unittest.mock import Mock, patch

import requests
from requests.exceptions import HTTPError
from test_utils import WisdomServiceLogAwareTestCase
from users.authz_checker import AMSCheck, CIAMCheck, Token


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

        # Ensure we server the cached result the second time
        m_r.json.reset_mock()
        self.assertEqual(my_token.get(), "foo_bar")
        self.assertEqual(m_r.json.call_count, 0)

    @patch("requests.post")
    def test_token_refresh_with_500_status_code(self, m_post):
        m_r = Mock()
        m_r.status_code = 500
        m_post.return_value = m_r

        with self.assertLogs(logger='root', level='ERROR') as log:
            my_token = Token("foo", "bar")
            self.assertIsNone(my_token.refresh())
            self.assertInLog("Unexpected error code (500) returned by SSO service", log)

    def test_ciam_check(self):
        m_r = Mock()
        m_r.json.return_value = {"result": True}
        m_r.status_code = 200

        checker = CIAMCheck("foo", "bar", "https://sso.redhat.com", "https://some-api.server.host")
        checker._token = Mock()
        checker._session = Mock()
        checker._session.post.return_value = m_r
        self.assertTrue(checker.check("my_id", "my_name", "123"))
        checker._session.post.assert_called_with(
            'https://some-api.server.host/v1alpha/check',
            json={
                'subject': 'my_id',
                'operation': 'access',
                'resourcetype': 'license',
                'resourceid': '123/smarts',
            },
            timeout=0.8,
        )

    def test_ciam_check_with_500_status_code(self):
        m_r = Mock()
        m_r.status_code = 500

        checker = CIAMCheck("foo", "bar", "https://sso.redhat.com", "https://some-api.server.host")
        checker._token = Mock()
        checker._session = Mock()
        checker._session.post.return_value = m_r

        with self.assertLogs(logger='root', level='ERROR') as log:
            self.assertFalse(checker.check("my_id", "my_name", "123"))
            self.assertInLog("Unexpected error code (500) returned by CIAM backend", log)

    def test_ciam_self_test_success(self):
        m_r = Mock()
        m_r.status_code = 200

        checker = CIAMCheck("foo", "bar", "https://sso.redhat.com", "https://some-api.server.host")
        checker._token = Mock()
        checker._session = Mock()
        checker._session.post.return_value = m_r
        try:
            checker.self_test()
        except HTTPError:
            self.fail("self_test() should not have raised an exception.")

    def test_ciam_self_test_failure(self):
        r = requests.models.Response()
        r.status_code = 500

        checker = CIAMCheck("foo", "bar", "https://sso.redhat.com", "https://some-api.server.host")
        checker._token = Mock()
        checker._session = Mock()
        checker._session.post.return_value = r

        with self.assertRaises(HTTPError):
            checker.self_test()

    def test_ams_get_ams_org(self):
        m_r = Mock()
        m_r.json.return_value = {"items": [{"id": "qwe"}]}
        m_r.status_code = 200

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.return_value = m_r
        self.assertEqual(checker.get_ams_org("123"), "qwe")
        checker._session.get.assert_called_with(
            'https://some-api.server.host/api/accounts_mgmt/v1/organizations',
            params={'search': "external_id='123'"},
            timeout=0.8,
        )

        # Ensure the second call is cached
        m_r.json.reset_mock()
        self.assertEqual(checker.get_ams_org("123"), "qwe")
        self.assertEqual(m_r.json.call_count, 0)

    def test_ams_get_ams_org_with_500_status_code(self):
        m_r = Mock()
        m_r.status_code = 500

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.return_value = m_r

        with self.assertLogs(logger='root', level='ERROR') as log:
            self.assertEqual(checker.get_ams_org("123"), "")
            self.assertInLog("Unexpected error code (500) returned by AMS backend (org)", log)

        # Ensure the second call is cached
        m_r.json.reset_mock()
        self.assertEqual(checker.get_ams_org("123"), "")
        self.assertEqual(m_r.json.call_count, 0)

    def test_ams_get_ams_org_with_empty_data(self):
        m_r = Mock()
        m_r.json.return_value = {"items": []}
        m_r.status_code = 200

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.return_value = m_r

        with self.assertLogs(logger='root', level='ERROR') as log:
            self.assertEqual(checker.get_ams_org("123"), "")
            self.assertInLog('Unexpected organization answer from AMS: data={"items": []}', log)
            self.assertInLog("IndexError: list index out of range", log)

    def test_ams_check(self):
        m_r = Mock()
        m_r.json.side_effect = [{"items": [{"id": "qwe"}]}, {"items": [{"id": "asd"}]}]
        m_r.status_code = 200

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.return_value = m_r
        self.assertTrue(checker.check("my_id", "my_name", "123"))
        checker._session.get.assert_called_with(
            'https://some-api.server.host/api/accounts_mgmt/v1/subscriptions',
            params={
                'search': "plan.id = 'AnsibleWisdom' AND status = 'Active' "
                "AND creator.username = 'my_name' AND organization_id='qwe'"
            },
            timeout=0.8,
        )

    def test_ams_check_with_500_status_code(self):
        m_r = Mock()
        m_r.status_code = 500

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.return_value = m_r

        with self.assertLogs(logger='root', level='ERROR') as log:
            self.assertFalse(checker.check("my_id", "my_name", "123"))
            self.assertInLog("Unexpected error code (500) returned by AMS backend (sub)", log)

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

        self.assertTrue(checker.rh_user_is_org_admin("user", "123"))
        checker._session.get.assert_called_with(
            'https://some-api.server.host/api/accounts_mgmt/v1/role_bindings',
            params={"search": "account.username = 'user' AND organization.id='123'"},
            timeout=0.8,
        )

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

        self.assertFalse(checker.rh_user_is_org_admin("user", "123"))
        checker._session.get.assert_called_with(
            'https://some-api.server.host/api/accounts_mgmt/v1/role_bindings',
            params={"search": "account.username = 'user' AND organization.id='123'"},
            timeout=0.8,
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

        self.assertFalse(checker.rh_user_is_org_admin("user", "123"))

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

        self.assertFalse(checker.rh_user_is_org_admin("user", "123"))

    def test_rh_user_is_org_admin_timeout(self):
        def side_effect(*args, **kwargs):
            raise requests.exceptions.Timeout()

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.side_effect = side_effect
        with self.assertLogs(logger='root', level='ERROR') as log:
            self.assertFalse(checker.rh_user_is_org_admin("user", "123"))
            self.assertInLog(AMSCheck.ERROR_AMS_CONNECTION_TIMEOUT, log)

    def test_rh_user_is_org_admin_network_error(self):
        m_r = Mock()
        m_r.status_code = 500

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.return_value = m_r

        with self.assertLogs(logger='root', level='ERROR') as log:
            self.assertFalse(checker.rh_user_is_org_admin("user", "123"))
            self.assertInLog(
                "Unexpected error code (500) returned by AMS backend when listing role bindings",
                log,
            )

    def test_rh_org_has_subscription(self):
        m_r = Mock()
        m_r.json.side_effect = [
            {"items": [{"id": "rdgdfhbrdb"}]},
            {"items": [{"subscription": {"status": "Active"}}], "total": 1},
        ]
        m_r.status_code = 200

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.return_value = m_r

        self.assertTrue(checker.rh_org_has_subscription("123"))
        checker._session.get.assert_called_with(
            (
                'https://some-api.server.host'
                '/api/accounts_mgmt/v1/organizations/rdgdfhbrdb/resource_quota'
            ),
            params={"search": "sku = 'FakeAnsibleWisdom' AND sku_count > 0"},
            timeout=0.8,
        )

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

        self.assertFalse(checker.rh_org_has_subscription("123"))
        checker._session.get.assert_called_with(
            (
                'https://some-api.server.host'
                '/api/accounts_mgmt/v1/organizations/rdgdfhbrdb/resource_quota'
            ),
            params={"search": "sku = 'FakeAnsibleWisdom' AND sku_count > 0"},
            timeout=0.8,
        )

    def test_rh_org_has_subscription_timeout(self):
        def side_effect(*args, **kwargs):
            raise requests.exceptions.Timeout()

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.side_effect = side_effect
        with self.assertLogs(logger='root', level='ERROR') as log:
            self.assertFalse(checker.rh_org_has_subscription("123"))
            self.assertInLog(AMSCheck.ERROR_AMS_CONNECTION_TIMEOUT, log)

    def test_rh_org_has_subscription_network_error(self):
        m_r = Mock()
        m_r.status_code = 500

        checker = self.get_default_ams_checker()
        checker._token = Mock()
        checker._session = Mock()
        checker._session.get.return_value = m_r

        with self.assertLogs(logger='root', level='ERROR') as log:
            self.assertFalse(checker.rh_org_has_subscription("123"))
            self.assertInLog(
                "Unexpected error code (500) returned by AMS backend when listing resource_quota",
                log,
            )

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

        with self.assertLogs(logger='root', level='ERROR') as log:
            self.assertFalse(checker.rh_org_has_subscription("123"))
            self.assertInLog("Unexpected resource_quota answer from AMS", log)
