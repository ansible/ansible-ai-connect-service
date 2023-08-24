from http import HTTPStatus
from unittest.mock import Mock, patch

from ai.api.aws.wca_secret_manager import Suffixes, WcaSecretManager
from ai.api.tests.test_views import WisdomServiceAPITestCaseBase
from django.apps import apps
from django.urls import reverse
from django.utils import timezone

mockSecretManager = Mock(WcaSecretManager)


class TestWCAModelIdView(WisdomServiceAPITestCaseBase):
    def test_authentication_error(self):
        # self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_model_id', kwargs={'org_id': '1'}))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    def test_get_model_api_when_undefined(self):
        self.client.force_authenticate(user=self.user)

        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mockSecretManager,
        ):
            mockSecretManager.get_secret.return_value = None
            r = self.client.get(reverse('wca_model_id', kwargs={'org_id': 'unknown'}))
            self.assertEqual(r.status_code, HTTPStatus.NOT_FOUND)
            mockSecretManager.get_secret.assert_called_with('unknown', Suffixes.MODEL_ID)

    def test_get_model_id_when_defined(self):
        self.client.force_authenticate(user=self.user)

        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mockSecretManager,
        ):
            mockSecretManager.get_secret.return_value = {
                'SecretString': 'secret_model_id',
                'CreatedDate': timezone.now().isoformat(),
            }
            r = self.client.get(reverse('wca_model_id', kwargs={'org_id': '1'}))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertEqual(r.data['model_id'], 'secret_model_id')
            mockSecretManager.get_secret.assert_called_with('1', Suffixes.MODEL_ID)

    def test_create_model_id(self):
        self.client.force_authenticate(user=self.user)

        # ModelId should initially not exist
        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mockSecretManager,
        ):
            mockSecretManager.get_secret.return_value = None
            r = self.client.get(reverse('wca_model_id', kwargs={'org_id': '1'}))
            self.assertEqual(r.status_code, HTTPStatus.NOT_FOUND)
            mockSecretManager.get_secret.assert_called_with('1', Suffixes.MODEL_ID)

            # Set ModelId
            r = self.client.post(
                reverse('wca_model_id', kwargs={'org_id': '1'}),
                data='secret_model_id',
                content_type='text/plain',
            )
            self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)
            mockSecretManager.save_secret.assert_called_with(
                '1', Suffixes.MODEL_ID, 'secret_model_id'
            )

            # Check ModelId was stored
            mockSecretManager.get_secret.return_value = {
                'SecretString': 'secret_model_id',
                'CreatedDate': timezone.now().isoformat(),
            }
            r = self.client.get(reverse('wca_model_id', kwargs={'org_id': '1'}))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertEqual(r.data['model_id'], 'secret_model_id')
            mockSecretManager.get_secret.assert_called_with('1', Suffixes.MODEL_ID)

    def test_update_model_id(self):
        self.client.force_authenticate(user=self.user)

        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mockSecretManager,
        ):
            # ModelId should exist
            mockSecretManager.get_secret.return_value = {
                'SecretString': 'secret_model_id',
                'CreatedDate': timezone.now().isoformat(),
            }
            r = self.client.get(reverse('wca_model_id', kwargs={'org_id': '1'}))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            mockSecretManager.get_secret.assert_called_with('1', Suffixes.MODEL_ID)

            # Set ModelId
            r = self.client.post(
                reverse('wca_model_id', kwargs={'org_id': '1'}),
                data='a-new-key',
                content_type='text/plain',
            )
            self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)
            mockSecretManager.save_secret.assert_called_with('1', Suffixes.MODEL_ID, 'a-new-key')

            # Check ModelId was stored
            mockSecretManager.get_secret.return_value = {
                'SecretString': 'secret_model_id',
                'CreatedDate': timezone.now().isoformat(),
            }
            r = self.client.get(reverse('wca_model_id', kwargs={'org_id': '1'}))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertEqual(r.data['model_id'], 'secret_model_id')
            mockSecretManager.get_secret.assert_called_with('1', Suffixes.MODEL_ID)
