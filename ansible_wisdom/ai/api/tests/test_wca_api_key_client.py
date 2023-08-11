from unittest.mock import patch

import botocore.client
from rest_framework.test import APITestCase

from ..aws.wca_api_keys_client import SECRET_KEY_PREFIX, WcaApiKeysClient


class TestWcaApiKeyClient(APITestCase):
    def nop(self):
        pass

    def testInitializer(self):
        replica_regions = "not,a,list"
        with self.assertRaises(TypeError):
            WcaApiKeysClient('dummy', 'dummy', 'dummy', 'dummy', replica_regions)

    def testGetSecretName(self):
        org_id = 'org_123'
        self.assertEqual(
            WcaApiKeysClient.get_secret_id(org_id), f'{SECRET_KEY_PREFIX}/{org_id}/wca_key'
        )
