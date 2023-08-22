from unittest.mock import Mock, patch

import boto3
import botocore
from ai.api.aws.exceptions import WcaSecretManagerError
from ai.api.aws.wca_secret_manager import SECRET_KEY_PREFIX, WcaSecretManager
from botocore.exceptions import ClientError
from rest_framework.test import APITestCase

ORG_ID = "org_123"
SECRET_VALUE = "secret"


class TestWcaApiKeyClient(APITestCase):
    def nop(self):
        pass

    def test_initializer(self):
        replica_regions = "not,a,list"
        with self.assertRaises(TypeError):
            WcaSecretManager('dummy', 'dummy', 'dummy', 'dummy', replica_regions)

    def test_get_secret_name(self):
        self.assertEqual(
            WcaSecretManager.get_secret_id(ORG_ID), f'{SECRET_KEY_PREFIX}/{ORG_ID}/wca_key'
        )

    def test_get_key(self):
        def mock_api_call(_, operation_name, kwarg):
            if operation_name == "GetSecretValue" and kwarg[
                "SecretId"
            ] == WcaSecretManager.get_secret_id(ORG_ID):
                return {"SecretString": SECRET_VALUE}
            else:
                raise ClientError({}, operation_name)

        with patch("botocore.client.BaseClient._make_api_call", new=mock_api_call):
            client = WcaSecretManager('dummy', 'dummy', 'dummy', 'dummy', [])
            response = client.get_key(ORG_ID)
            self.assertEqual(response['SecretString'], SECRET_VALUE)

    def test_get_key_error(self):
        def mock_api_call(_, operation_name, kwarg):
            raise ClientError({}, operation_name)

        with patch("botocore.client.BaseClient._make_api_call", new=mock_api_call):
            client = WcaSecretManager('dummy', 'dummy', 'dummy', 'dummy', [])
            with self.assertRaises(WcaSecretManagerError):
                with self.assertLogs(logger='root', level='ERROR') as log:
                    client.get_key(ORG_ID)
                    expected_log = (
                        "ERROR:ai.api.aws.wca_secret_manager"
                        + f"Error reading secret for org_id '{ORG_ID}'"
                    )
                    self.assertTrue(expected_log in log.output)

    def test_key_exist(self):
        def mock_api_call(_, operation_name, kwarg):
            if operation_name == "GetSecretValue" and kwarg[
                "SecretId"
            ] == WcaSecretManager.get_secret_id(ORG_ID):
                return {"SecretString": SECRET_VALUE}
            else:
                c = boto3.client('secretsmanager', region_name="eu-central-1")
                raise c.exceptions.ResourceNotFoundException({}, operation_name)

        with patch("botocore.client.BaseClient._make_api_call", new=mock_api_call):
            client = WcaSecretManager('dummy', 'dummy', 'dummy', 'dummy', [])
            self.assertEqual(client.key_exists(ORG_ID), True)
            self.assertEqual(client.key_exists('does_not_exist'), False)

    def test_save_new_key(self):
        def mock_api_call(_, operation_name, kwarg):
            if operation_name == "GetSecretValue":
                c = boto3.client('secretsmanager', region_name="eu-central-1")
                raise c.exceptions.ResourceNotFoundException({}, operation_name)
            elif operation_name == "CreateSecret" and kwarg[
                "Name"
            ] == WcaSecretManager.get_secret_id(ORG_ID):
                return kwarg
            else:
                raise ClientError({}, operation_name)

        with patch("botocore.client.BaseClient._make_api_call", new=mock_api_call):
            client = WcaSecretManager('dummy', 'dummy', 'dummy', 'dummy', [])
            response = client.save_key(ORG_ID, SECRET_VALUE)
            self.assertEqual(response, client.get_secret_id(ORG_ID))

    def test_update_key(self):
        def mock_api_call(_, operation_name, kwarg):
            if operation_name == "GetSecretValue":
                return {'SecretString': kwarg['SecretId']}
            elif operation_name == "PutSecretValue" and kwarg[
                "SecretId"
            ] == WcaSecretManager.get_secret_id(ORG_ID):
                return {"Name": kwarg["SecretId"]}
            else:
                raise ClientError({}, operation_name)

        with patch("botocore.client.BaseClient._make_api_call", new=mock_api_call):
            client = WcaSecretManager('dummy', 'dummy', 'dummy', 'dummy', [])
            response = client.save_key(ORG_ID, SECRET_VALUE)
            self.assertEqual(response, client.get_secret_id(ORG_ID))

    def test_save_new_key_fails(self):
        with patch("boto3.client"):
            client = WcaSecretManager('dummy', 'dummy', 'dummy', 'dummy', [])
            client._client.create_secret = Mock(side_effect=ClientError({}, "nop"))
            client.key_exists = Mock(return_value=False)
            with self.assertRaises(WcaSecretManagerError):
                client.save_key(ORG_ID, SECRET_VALUE)

    def test_save_key_fails(self):
        with patch("boto3.client"):
            client = WcaSecretManager('dummy', 'dummy', 'dummy', 'dummy', [])
            client._client.put_secret_value = Mock(side_effect=ClientError({}, "nop"))
            client.key_exists = Mock(return_value=True)
            with self.assertRaises(WcaSecretManagerError):
                client.save_key(ORG_ID, SECRET_VALUE)

    def test_delete_key(self):
        def mock_api_call(_, operation_name, kwarg):
            if operation_name == "RemoveRegionsFromReplication":
                return None
            if operation_name == "DeleteSecret" and kwarg["SecretId"] == client.get_secret_id(
                ORG_ID
            ):
                return None
            raise ClientError({}, operation_name)

        with patch("botocore.client.BaseClient._make_api_call", new=mock_api_call):
            client = WcaSecretManager('dummy', 'dummy', 'dummy', 'dummy', [])
            self.assertIsNone(client.delete_key(ORG_ID))

    def test_delete_key_remove_invalid_region(self):
        def mock_api_call(_, operation_name, kwarg):
            if operation_name == "RemoveRegionsFromReplication":
                c = boto3.client('secretsmanager', region_name="eu-central-1")
                raise c.exceptions.InvalidParameterException({}, operation_name)
            return None

        with patch("botocore.client.BaseClient._make_api_call", new=mock_api_call):
            client = WcaSecretManager('dummy', 'dummy', 'dummy', 'dummy', [])
            with self.assertLogs(logger='root', level='ERROR') as log:
                client.delete_key(ORG_ID)
                expected_log = (
                    "ERROR:ai.api.aws.wca_secret_manager:"
                    + f"Error removing replica regions, invalid region(s) for org_id '{ORG_ID}'"
                )
                self.assertTrue(expected_log in log.output)

    def test_delete_key_remove_regions_not_found(self):
        def mock_api_call(_, operation_name, kwarg):
            if operation_name == "RemoveRegionsFromReplication":
                c = boto3.client('secretsmanager', region_name="eu-central-1")
                raise c.exceptions.ResourceNotFoundException({}, operation_name)
            return None

        with patch("botocore.client.BaseClient._make_api_call", new=mock_api_call):
            client = WcaSecretManager('dummy', 'dummy', 'dummy', 'dummy', [])
            with self.assertLogs(logger='root', level='ERROR') as log:
                client.delete_key(ORG_ID)
                expected_log = (
                    "ERROR:ai.api.aws.wca_secret_manager:"
                    + f"Error removing replica regions, secret does not exist for org_id '{ORG_ID}'"
                )
                self.assertTrue(expected_log in log.output)

    def test_delete_key_remove_regions_client_error(self):
        def mock_api_call(_, operation_name, kwarg):
            if operation_name == "RemoveRegionsFromReplication":
                raise ClientError({}, operation_name)
            return None

        with patch("botocore.client.BaseClient._make_api_call", new=mock_api_call):
            client = WcaSecretManager('dummy', 'dummy', 'dummy', 'dummy', [])
            with self.assertLogs(logger='root', level='ERROR') as log:
                client.delete_key(ORG_ID)
                expected_log = (
                    "ERROR:ai.api.aws.wca_secret_manager:"
                    + f"Error removing replica regions for org_id '{ORG_ID}'"
                )
                self.assertTrue(expected_log in log.output)

    def test_delete_key_client_error(self):
        def mock_api_call(_, operation_name, kwarg):
            if operation_name == "DeleteSecret":
                raise ClientError({}, operation_name)
            return None

        with patch("botocore.client.BaseClient._make_api_call", new=mock_api_call):
            client = WcaSecretManager('dummy', 'dummy', 'dummy', 'dummy', [])
            with self.assertRaises(WcaSecretManagerError):
                with self.assertLogs(logger='root', level='ERROR') as log:
                    client.delete_key(ORG_ID)
                    expected_log = (
                        "ERROR:ansible_wisdom.ai.api.aws.wca_secret_manager:"
                        + f"Error removing secret for org_id '{ORG_ID}'"
                    )
                    self.assertTrue(expected_log in log.output)
