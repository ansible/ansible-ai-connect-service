from http import HTTPStatus
from unittest.mock import patch

from ai.api.aws.wca_secret_manager import WcaSecretManager
from ai.api.tests.test_views import WisdomServiceAPITestCaseBase
from django.apps import apps
from django.urls import reverse
from django.utils import timezone


class DummySecretManager(WcaSecretManager):
    __storage__: dict[str, object] = {}

    def __init__(self, storage: dict[str, object]):
        super().__init__(None, None, None, None, [])
        self.__storage__ = storage

    def get_key(self, org_id):
        return self.__storage__.get(org_id)

    def save_key(self, org_id, key):
        self.__storage__[org_id] = {'key': key, 'CreatedDate': timezone.now().isoformat()}


class TestWCAKeyView(WisdomServiceAPITestCaseBase):
    def test_authentication_error(self):
        # self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca', kwargs={'org_id': '1'}))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    def test_get_unknown_org_id(self):
        self.client.force_authenticate(user=self.user)

        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            DummySecretManager({}),
        ):
            r = self.client.get(reverse('wca', kwargs={'org_id': 'unknown'}))
            self.assertEqual(r.status_code, HTTPStatus.NOT_FOUND)

    def test_get_known_org_id(self):
        self.client.force_authenticate(user=self.user)

        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            DummySecretManager({'1': {'CreatedDate': timezone.now().isoformat()}}),
        ):
            r = self.client.get(reverse('wca', kwargs={'org_id': '1'}))
            self.assertEqual(r.status_code, HTTPStatus.OK)

    def test_set_unknown_org_id(self):
        self.client.force_authenticate(user=self.user)

        # Key should initially not exist
        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            DummySecretManager({}),
        ):
            r = self.client.get(reverse('wca', kwargs={'org_id': '1'}))
            self.assertEqual(r.status_code, HTTPStatus.NOT_FOUND)

            # Set Key
            r = self.client.post(
                reverse('wca', kwargs={'org_id': '1'}), data='a-new-key', content_type='text/plain'
            )
            self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)

            # Check Key was stored
            r = self.client.get(reverse('wca', kwargs={'org_id': '1'}))
            self.assertEqual(r.status_code, HTTPStatus.OK)

    def test_set_known_org_id(self):
        self.client.force_authenticate(user=self.user)

        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            DummySecretManager({'1': {'CreatedDate': timezone.now().isoformat()}}),
        ):
            # Key should exist
            r = self.client.get(reverse('wca', kwargs={'org_id': '1'}))
            self.assertEqual(r.status_code, HTTPStatus.OK)

            # Set Key
            r = self.client.post(
                reverse('wca', kwargs={'org_id': '1'}), data='a-new-key', content_type='text/plain'
            )
            self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)

            # Check Key was stored
            r = self.client.get(reverse('wca', kwargs={'org_id': '1'}))
            self.assertEqual(r.status_code, HTTPStatus.OK)
