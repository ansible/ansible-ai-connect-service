from unittest.mock import patch

import boto3
from ai.api.aws.exceptions import WcaSecretManagerError
from ai.api.aws.wca_secret_manager import SECRET_KEY_PREFIX, Suffixes, WcaSecretManager
from botocore.exceptions import ClientError
from rest_framework.test import APITestCase
from test_utils import WisdomServiceLogAwareTestCase

ORG_ID = "org_123"
SECRET_VALUE = "secret"


class TestWcaApiKeyClient(APITestCase, WisdomServiceLogAwareTestCase):
    def nop(self):
        pass

    def test_initializer(self):
        replica_regions = "not,a,list"
        with self.assertRaises(TypeError):
            WcaSecretManager('dummy', 'dummy', 'dummy', 'dummy', replica_regions)

    def test_get_secret_name(self):
        self.assertEqual(
            WcaSecretManager.get_secret_id(ORG_ID, Suffixes.API_KEY),
            f'{SECRET_KEY_PREFIX}/{ORG_ID}/{Suffixes.API_KEY.value}',
        )

    def test_get_key(self):
        def mock_api_call(_, operation_name, kwarg):
            if operation_name == "GetSecretValue" and kwarg[
                "SecretId"
            ] == WcaSecretManager.get_secret_id(ORG_ID, Suffixes.API_KEY):
                return {"SecretString": SECRET_VALUE}
            else:
                raise ClientError({}, operation_name)

        with patch("botocore.client.BaseClient._make_api_call", new=mock_api_call):
            client = WcaSecretManager('dummy', 'dummy', 'dummy', 'dummy', [])
            response = client.get_secret(ORG_ID, Suffixes.API_KEY)
            self.assertEqual(response['SecretString'], SECRET_VALUE)

    def test_get_key_error(self):
        def mock_api_call(_, operation_name, kwarg):
            raise ClientError({}, operation_name)

        with patch("botocore.client.BaseClient._make_api_call", new=mock_api_call):
            client = WcaSecretManager('dummy', 'dummy', 'dummy', 'dummy', [])
            with self.assertRaises(WcaSecretManagerError):
                with self.assertLogs(logger='root', level='ERROR') as log:
                    client.get_secret(ORG_ID, Suffixes.API_KEY)
                    self.assertInLog(f"Error reading secret for org_id '{ORG_ID}'", log)

    def test_key_exist(self):
        def mock_api_call(_, operation_name, kwarg):
            if operation_name == "GetSecretValue" and kwarg[
                "SecretId"
            ] == WcaSecretManager.get_secret_id(ORG_ID, Suffixes.API_KEY):
                return {"SecretString": SECRET_VALUE}
            else:
                c = boto3.client('secretsmanager', region_name="eu-central-1")
                raise c.exceptions.ResourceNotFoundException({}, operation_name)

        with patch("botocore.client.BaseClient._make_api_call", new=mock_api_call):
            client = WcaSecretManager('dummy', 'dummy', 'dummy', 'dummy', [])
            self.assertEqual(client.secret_exists(ORG_ID, Suffixes.API_KEY), True)
            self.assertEqual(client.secret_exists('does_not_exist', Suffixes.API_KEY), False)

    def test_save_new_key(self):
        def mock_api_call(_, operation_name, kwarg):
            if operation_name == "GetSecretValue":
                c = boto3.client('secretsmanager', region_name="eu-central-1")
                raise c.exceptions.ResourceNotFoundException({}, operation_name)
            elif operation_name == "CreateSecret" and kwarg[
                "Name"
            ] == WcaSecretManager.get_secret_id(ORG_ID, Suffixes.API_KEY):
                return kwarg
            else:
                raise ClientError({}, operation_name)

        with patch("botocore.client.BaseClient._make_api_call", new=mock_api_call):
            client = WcaSecretManager('dummy', 'dummy', 'dummy', 'dummy', [])
            response = client.save_secret(ORG_ID, Suffixes.API_KEY, SECRET_VALUE)
            self.assertEqual(response, client.get_secret_id(ORG_ID, Suffixes.API_KEY))

    def test_update_key(self):
        def mock_api_call(_, operation_name, kwarg):
            if operation_name == "GetSecretValue":
                return {'SecretString': kwarg['SecretId']}
            elif operation_name == "PutSecretValue" and kwarg[
                "SecretId"
            ] == WcaSecretManager.get_secret_id(ORG_ID, Suffixes.API_KEY):
                return {"Name": kwarg["SecretId"]}
            else:
                raise ClientError({}, operation_name)

        with patch("botocore.client.BaseClient._make_api_call", new=mock_api_call):
            client = WcaSecretManager('dummy', 'dummy', 'dummy', 'dummy', [])
            response = client.save_secret(ORG_ID, Suffixes.API_KEY, SECRET_VALUE)
            self.assertEqual(response, client.get_secret_id(ORG_ID, Suffixes.API_KEY))

    def test_save_key_fails(self):
        def mock_api_call(_, operation_name, kwarg):
            if operation_name == "GetSecretValue":
                raise ClientError({}, operation_name)

        with patch("botocore.client.BaseClient._make_api_call", new=mock_api_call):
            client = WcaSecretManager('dummy', 'dummy', 'dummy', 'dummy', [])
            with self.assertRaises(WcaSecretManagerError):
                client.save_secret(ORG_ID, Suffixes.API_KEY, SECRET_VALUE)

    def test_delete_key(self):
        def mock_api_call(_, operation_name, kwarg):
            if operation_name == "RemoveRegionsFromReplication":
                return None
            if operation_name == "DeleteSecret" and kwarg["SecretId"] == client.get_secret_id(
                ORG_ID, Suffixes.API_KEY
            ):
                return None
            raise ClientError({}, operation_name)

        with patch("botocore.client.BaseClient._make_api_call", new=mock_api_call):
            client = WcaSecretManager('dummy', 'dummy', 'dummy', 'dummy', [])
            self.assertIsNone(client.delete_secret(ORG_ID, Suffixes.API_KEY))

    def test_delete_key_remove_invalid_region(self):
        def mock_api_call(_, operation_name, kwarg):
            if operation_name == "RemoveRegionsFromReplication":
                c = boto3.client('secretsmanager', region_name="eu-central-1")
                raise c.exceptions.InvalidParameterException({}, operation_name)
            return None

        with patch("botocore.client.BaseClient._make_api_call", new=mock_api_call):
            client = WcaSecretManager('dummy', 'dummy', 'dummy', 'dummy', [])
            with self.assertLogs(logger='root', level='ERROR') as log:
                client.delete_secret(ORG_ID, Suffixes.API_KEY)
                self.assertInLog(
                    f"Error removing replica regions, invalid region(s) for org_id '{ORG_ID}'", log
                )

    def test_delete_key_remove_regions_not_found(self):
        def mock_api_call(_, operation_name, kwarg):
            if operation_name == "RemoveRegionsFromReplication":
                c = boto3.client('secretsmanager', region_name="eu-central-1")
                raise c.exceptions.ResourceNotFoundException({}, operation_name)
            return None

        with patch("botocore.client.BaseClient._make_api_call", new=mock_api_call):
            client = WcaSecretManager('dummy', 'dummy', 'dummy', 'dummy', [])
            with self.assertLogs(logger='root', level='ERROR') as log:
                client.delete_secret(ORG_ID, Suffixes.API_KEY)
                self.assertInLog(
                    f"Error removing replica regions, Secret does not exist for org_id '{ORG_ID}'",
                    log,
                )

    def test_delete_key_remove_regions_client_error(self):
        def mock_api_call(_, operation_name, kwarg):
            if operation_name == "RemoveRegionsFromReplication":
                raise ClientError({}, operation_name)
            return None

        with patch("botocore.client.BaseClient._make_api_call", new=mock_api_call):
            client = WcaSecretManager('dummy', 'dummy', 'dummy', 'dummy', [])
            with self.assertLogs(logger='root', level='ERROR') as log:
                client.delete_secret(ORG_ID, Suffixes.API_KEY)
                self.assertInLog(
                    "An error occurred",
                    log,
                )

    def test_delete_key_client_error(self):
        def mock_api_call(_, operation_name, kwarg):
            if operation_name == "DeleteSecret":
                raise ClientError({}, operation_name)
            return None

        with patch("botocore.client.BaseClient._make_api_call", new=mock_api_call):
            client = WcaSecretManager('dummy', 'dummy', 'dummy', 'dummy', [])
            with self.assertRaises(WcaSecretManagerError):
                with self.assertLogs(logger='root', level='ERROR') as log:
                    client.delete_secret(ORG_ID, Suffixes.API_KEY)
                    self.assertInLog(f"Error removing secret for org_id '{ORG_ID}'", log)
