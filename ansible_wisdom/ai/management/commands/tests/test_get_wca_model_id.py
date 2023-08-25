from io import StringIO
from unittest.mock import patch

from ai.api.aws.wca_secret_manager import Suffixes
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase


class GetWcaModelIdCommandTestCase(TestCase):
    def test_missing_required_args(self):
        with self.assertRaisesMessage(
            CommandError, 'Error: the following arguments are required: org_id'
        ):
            call_command('get_wca_model_id')

    @patch("ai.management.commands._base_wca_command.WcaSecretManager")
    def test_model_id_found(self, mock_secret_manager):
        instance = mock_secret_manager.return_value
        instance.get_secret.return_value = {"model_id": "mock_model_id", "CreatedDate": "xxx"}

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            call_command('get_wca_model_id', 'mock_org_id')
            instance.get_secret.assert_called_once_with("mock_org_id", Suffixes.MODEL_ID)
            captured_output = mock_stdout.getvalue()
            self.assertIn(
                "Model Id for orgId 'mock_org_id' found. Id: mock_model_id, Last updated: xxx",
                captured_output,
            )

    @patch("ai.management.commands._base_wca_command.WcaSecretManager")
    def test_model_id_not_found(self, mock_secret_manager):
        instance = mock_secret_manager.return_value
        instance.get_secret.return_value = None

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            call_command('get_wca_model_id', 'mock_org_id')
            instance.get_secret.assert_called_once_with("mock_org_id", Suffixes.MODEL_ID)
            captured_output = mock_stdout.getvalue()
            self.assertIn("No Model Id for orgId 'mock_org_id' found.", captured_output)
