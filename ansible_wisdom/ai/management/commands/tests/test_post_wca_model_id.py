from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from ansible_wisdom.ai.api.aws.wca_secret_manager import Suffixes


class PostWcaModelIdCommandTestCase(TestCase):
    def test_missing_required_args(self):
        with self.assertRaisesMessage(
            CommandError, 'Error: the following arguments are required: org_id, secret'
        ):
            call_command('post_wca_model_id')

    @patch("ansible_wisdom.ai.management.commands._base_wca_command.AWSSecretManager")
    def test_model_id_saved(self, mock_secret_manager):
        instance = mock_secret_manager.return_value
        instance.save_secret.return_value = "mock_model_id_name"

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            call_command('post_wca_model_id', 'mock_org_id', 'mock_model_id')
            instance.save_secret.assert_called_once_with(
                "mock_org_id", Suffixes.MODEL_ID, "mock_model_id"
            )
            captured_output = mock_stdout.getvalue()
            self.assertIn(
                "Model Id for orgId 'mock_org_id' stored as: mock_model_id_name", captured_output
            )
