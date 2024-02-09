from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from ansible_wisdom.ai.api.aws.wca_secret_manager import Suffixes


class DeleteWcaKeyCommandTestCase(TestCase):
    def test_missing_required_args(self):
        with self.assertRaisesMessage(
            CommandError, 'Error: the following arguments are required: org_id'
        ):
            call_command('delete_wca_key')

    @patch("ansible_wisdom.ai.management.commands._base_wca_command.AWSSecretManager")
    def test_key_deleted(self, mock_secret_manager):
        instance = mock_secret_manager.return_value

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            call_command('delete_wca_key', 'mock_org_id')
            instance.delete_secret.assert_called_once_with("mock_org_id", Suffixes.API_KEY)
            captured_output = mock_stdout.getvalue()
            self.assertIn("API Key for orgId 'mock_org_id' deleted.", captured_output)
