from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase


class PostWcaKeyCommandTestCase(TestCase):
    def test_missing_required_args(self):
        with self.assertRaisesMessage(
            CommandError, 'Error: the following arguments are required: org_id, key'
        ):
            call_command('post_wca_key')

    @patch("ai.management.commands.post_wca_key.WcaSecretManager")
    def test_key_saved(self, mock_secret_manager):
        instance = mock_secret_manager.return_value
        instance.save_key.return_value = "mock_key_name"

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            call_command('post_wca_key', 'mock_org_id', 'mock_key')
            instance.save_key.assert_called_once_with("mock_org_id", "mock_key")
            captured_output = mock_stdout.getvalue()
            self.assertIn(
                "API Key for orgId 'mock_org_id' stored as: mock_key_name", captured_output
            )
