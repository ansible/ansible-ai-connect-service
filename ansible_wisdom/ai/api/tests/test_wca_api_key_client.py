from unittest.mock import patch

from rest_framework.test import APITestCase

from ..aws.wca_api_keys_client import SECRET_KEY_PREFIX, WcaApiKeysClient


class TestWcaApiKeyClient(APITestCase):
    def nop(self):
        pass

    def testGetSecretName(self):
        with patch.object(WcaApiKeysClient, '__init__', self.nop):
            org_id = 'org_123'
            client = WcaApiKeysClient('dummy', 'dummy', 'dummy', 'dummy', [])
            self.assertEqual(client.__get_secret_id('org123'), f'{SECRET_KEY_PREFIX}//{org_id}')
