from http import HTTPStatus
from unittest.mock import Mock, patch

from ai.api.aws.wca_secret_manager import WcaSecretManager
from ai.api.tests.test_views import WisdomServiceAPITestCaseBase
from django.apps import apps
from django.urls import reverse
from django.utils import timezone

mockSecretManager = Mock(WcaSecretManager)


class TestWCAKeyView(WisdomServiceAPITestCaseBase):
    def test_authentication_error(self):
        # self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca', kwargs={'org_id': '1'}))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    def test_get_key_when_undefined(self):
        self.client.force_authenticate(user=self.user)

        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mockSecretManager,
        ):
            mockSecretManager.get_key.return_value = None
            r = self.client.get(reverse('wca', kwargs={'org_id': 'unknown'}))
            self.assertEqual(r.status_code, HTTPStatus.NOT_FOUND)
            mockSecretManager.get_key.assert_called_with('unknown')

    def test_get_key_when_defined(self):
        self.client.force_authenticate(user=self.user)

        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mockSecretManager,
        ):
            mockSecretManager.get_key.return_value = {'CreatedDate': timezone.now().isoformat()}
            r = self.client.get(reverse('wca', kwargs={'org_id': '1'}))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            mockSecretManager.get_key.assert_called_with('1')

    def test_create_key(self):
        self.client.force_authenticate(user=self.user)

        # Key should initially not exist
        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mockSecretManager,
        ):
            mockSecretManager.get_key.return_value = None
            r = self.client.get(reverse('wca', kwargs={'org_id': '1'}))
            self.assertEqual(r.status_code, HTTPStatus.NOT_FOUND)
            mockSecretManager.get_key.assert_called_with('1')

            # Set Key
            r = self.client.post(
                reverse('wca', kwargs={'org_id': '1'}), data='a-new-key', content_type='text/plain'
            )
            self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)
            mockSecretManager.save_key.assert_called_with('1', 'a-new-key')

            # Check Key was stored
            mockSecretManager.get_key.return_value = {'CreatedDate': timezone.now().isoformat()}
            r = self.client.get(reverse('wca', kwargs={'org_id': '1'}))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            mockSecretManager.get_key.assert_called_with('1')

    def test_update_key(self):
        self.client.force_authenticate(user=self.user)

        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mockSecretManager,
        ):
            # Key should exist
            mockSecretManager.get_key.return_value = {'CreatedDate': timezone.now().isoformat()}
            r = self.client.get(reverse('wca', kwargs={'org_id': '1'}))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            mockSecretManager.get_key.assert_called_with('1')

            # Set Key
            r = self.client.post(
                reverse('wca', kwargs={'org_id': '1'}), data='a-new-key', content_type='text/plain'
            )
            self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)
            mockSecretManager.save_key.assert_called_with('1', 'a-new-key')

            # Check Key was stored
            mockSecretManager.get_key.return_value = {'CreatedDate': timezone.now().isoformat()}
            r = self.client.get(reverse('wca', kwargs={'org_id': '1'}))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            mockSecretManager.get_key.assert_called_with('1')
