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

from unittest.mock import Mock

from botocore.exceptions import ClientError
from rest_framework.test import APITestCase

from ansible_ai_connect.ai.api.aws.exceptions import (
    WcaSecretManagerError,
    WcaSecretManagerMissingCredentialsError,
)
from ansible_ai_connect.ai.api.aws.wca_secret_manager import (
    SECRET_KEY_PREFIX,
    AWSSecretManager,
    Suffixes,
)
from ansible_ai_connect.test_utils import WisdomServiceLogAwareTestCase

ORG_ID = "org_123"
SECRET_VALUE = "secret"


class MockResourceNotFoundException(Exception):
    pass


class MockInvalidParameterException(Exception):
    pass


class TestWcaApiKeyClient(APITestCase, WisdomServiceLogAwareTestCase):
    def nop(self):
        pass

    def setUp(self):
        super().setUp()
        self.m_boto3_client = Mock()
        self.m_boto3_client.exceptions.ResourceNotFoundException = MockResourceNotFoundException
        self.m_boto3_client.exceptions.InvalidParameterException = MockInvalidParameterException

        self.c = AWSSecretManager("dummy", "dummy", "dummy", "dummy", [])
        self.c._client = self.m_boto3_client

    def test_get_secret_name(self):
        self.assertEqual(
            AWSSecretManager.get_secret_id(ORG_ID, Suffixes.API_KEY),
            f"{SECRET_KEY_PREFIX}/{ORG_ID}/{Suffixes.API_KEY.value}",
        )

    def test_get_key(self):
        self.m_boto3_client.get_secret_value.return_value = {"SecretString": SECRET_VALUE}
        response = self.c.get_secret(ORG_ID, Suffixes.API_KEY)
        self.assertEqual(response["SecretString"], SECRET_VALUE)

    def test_get_key_error(self):
        self.m_boto3_client.get_secret_value.side_effect = ClientError({}, "raah")

        with self.assertRaises(WcaSecretManagerError):
            with self.assertLogs(logger="root", level="ERROR") as log:
                self.c.get_secret(ORG_ID, Suffixes.API_KEY)
                self.assertInLog(f"Error reading secret for org_id '{ORG_ID}'", log)

    def test_key_exist(self):
        self.m_boto3_client.get_secret_value.return_value = "foo"
        self.assertEqual(self.c.secret_exists(ORG_ID, Suffixes.API_KEY), True)

    def test_key_doesnt_exist(self):
        self.m_boto3_client.get_secret_value.return_value = None
        self.assertEqual(self.c.secret_exists("does_not_exist", Suffixes.API_KEY), False)

    def test_save_new_key(self):
        self.m_boto3_client.get_secret_value.return_value = None
        self.m_boto3_client.create_secret.return_value = {"Name": "wisdom"}
        self.c.save_secret(ORG_ID, Suffixes.API_KEY, SECRET_VALUE)
        self.m_boto3_client.create_secret.assert_called()

    def test_update_key(self):
        self.m_boto3_client.put_secret_value.return_value = {"Name": "wisdom"}
        self.m_boto3_client.get_secret_value.return_value = "exists"
        self.c.save_secret(ORG_ID, Suffixes.API_KEY, SECRET_VALUE)
        self.m_boto3_client.put_secret_value.assert_called()

    def test_save_new_key_fails(self):
        self.m_boto3_client.get_secret_value.return_value = None
        self.m_boto3_client.create_secret.side_effect = ClientError({}, "nop")
        with self.assertRaises(WcaSecretManagerError):
            self.c.save_secret(ORG_ID, Suffixes.API_KEY, SECRET_VALUE)

    def test_save_key_fails(self):
        self.m_boto3_client.get_secret.return_value = True
        self.m_boto3_client.put_secret_value.side_effect = ClientError({}, "nop")
        with self.assertRaises(WcaSecretManagerError):
            self.c.save_secret(ORG_ID, Suffixes.API_KEY, SECRET_VALUE)

    def test_delete_key(self):
        self.assertIsNone(self.c.delete_secret(ORG_ID, Suffixes.API_KEY))
        self.m_boto3_client.delete_secret.assert_called()

    def test_delete_key_remove_regions_not_found(self):
        self.m_boto3_client.remove_regions_from_replication.side_effect = (
            MockResourceNotFoundException
        )
        with self.assertLogs(logger="root", level="ERROR") as log:
            self.c.delete_secret(ORG_ID, Suffixes.API_KEY)
            self.assertInLog(
                f"Error removing replica regions, Secret does not exist for org_id '{ORG_ID}'",
                log,
            )

    def test_delete_key_remove_invalid_region(self):
        self.m_boto3_client.remove_regions_from_replication.side_effect = (
            MockInvalidParameterException
        )
        with self.assertLogs(logger="root", level="ERROR") as log:
            self.c.delete_secret(ORG_ID, Suffixes.API_KEY)
            self.assertInLog(
                f"Error removing replica regions, invalid region(s) for org_id '{ORG_ID}'", log
            )

    def test_delete_key_remove_regions_client_error(self):
        self.m_boto3_client.remove_regions_from_replication.side_effect = ClientError(
            {}, "An error occurred"
        )
        with self.assertLogs(logger="root", level="ERROR") as log:
            self.c.delete_secret(ORG_ID, Suffixes.API_KEY)
            self.assertInLog(
                "An error occurred",
                log,
            )

    def test_delete_key_client_error(self):
        self.m_boto3_client.delete_secret.side_effect = ClientError({}, "An error occurred")
        with self.assertRaises(WcaSecretManagerError):
            with self.assertLogs(logger="root", level="ERROR") as log:
                self.c.delete_secret(ORG_ID, Suffixes.API_KEY)
                self.assertInLog(f"Error removing Secret for org_id '{ORG_ID}'", log)

    def test_missing_creds_exception(self):
        c = AWSSecretManager("dummy", None, "dummy", "dummy", [])
        with self.assertRaises(WcaSecretManagerMissingCredentialsError):
            c.get_client()
