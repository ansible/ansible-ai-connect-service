from copy import copy
from importlib import reload
from unittest.mock import patch

import numpy as np
from django.test import override_settings
from opensearchpy import AWSV4SignerAuth, OpenSearch
from rest_framework.test import APITestCase
from sentence_transformers import SentenceTransformer

import ansible_wisdom.ai.search as search


class TestSearch(APITestCase):
    DUMMY_AI_SEARCH_SETTINGS = {
        'REGION': '*',
        'KEY': '*',
        'SECRET': '*',
        'HOST': '*',
        'PORT': '*',
        'USE_SSL': False,
        'VERIFY_CERTS': False,
        'MODEL': '*',
        'INDEX': '*',
    }

    DUMMY_AI_SEARCH_SETTINGS_WITH_EMPTY_HOST = copy(DUMMY_AI_SEARCH_SETTINGS)
    DUMMY_AI_SEARCH_SETTINGS_WITH_EMPTY_HOST['HOST'] = ''

    DUMMY_AI_SEARCH_SETTINGS_WITH_EMPTY_REGION = copy(DUMMY_AI_SEARCH_SETTINGS)
    DUMMY_AI_SEARCH_SETTINGS_WITH_EMPTY_REGION['REGION'] = ''

    DUMMY_AI_SEARCH_SETTINGS_WITH_EMPTY_REGION_AND_KEY = copy(
        DUMMY_AI_SEARCH_SETTINGS_WITH_EMPTY_REGION
    )
    DUMMY_AI_SEARCH_SETTINGS_WITH_EMPTY_REGION_AND_KEY['KEY'] = ''

    def nop(self, *args, **kwargs):
        pass

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        def search(self, index, body, _source):
            return {
                'hits': {
                    'hits': [
                        {
                            'fields': {
                                'repo_name': ['repo_name'],
                                'repo_url': ['repo_url'],
                                'path': ['path'],
                                'license': ['license'],
                                'data_source': ['data_source'],
                                'type': ['ansible_type'],
                            },
                            '_score': 0,
                        },
                    ],
                },
            }

    class DummySentenceTransformer:
        def encode(self, sentences=None, batch_size=None):
            return sentences

    @override_settings(ANSIBLE_AI_SEARCH=DUMMY_AI_SEARCH_SETTINGS)
    def test_initialize_OpenSearch(self):
        with patch.object(OpenSearch, '__init__', self.nop):
            with patch.object(SentenceTransformer, '__init__', self.nop):
                client, model = search.initialize_OpenSearch()
                self.assertIsNotNone(client)
                self.assertIsNotNone(model)

        with patch('ansible_wisdom.ai.search.client', self.DummyClient()):
            with patch('ansible_wisdom.ai.search.model', self.DummySentenceTransformer()):
                ret = search.search(np.array(1))
                self.assertIsNotNone(ret)

    @override_settings(ANSIBLE_AI_SEARCH=DUMMY_AI_SEARCH_SETTINGS_WITH_EMPTY_HOST)
    def test_skip_initializing_OpenSearch(self):
        with patch.object(OpenSearch, '__init__', self.nop):
            with patch.object(SentenceTransformer, '__init__', self.nop):
                client, model = search.initialize_OpenSearch()
                self.assertIsNone(client)
                self.assertIsNone(model)

    def test_search(self):
        with patch('ansible_wisdom.ai.search.client', self.DummyClient()):
            with patch('ansible_wisdom.ai.search.model', self.DummySentenceTransformer()):
                ret = search.search(np.array(1))
                self.assertIsNotNone(ret)

    def test_search_with_none_client(self):
        with patch('ansible_wisdom.ai.search.client', None):
            with self.assertRaises(Exception):
                search.search(np.array(1))

    @override_settings(ANSIBLE_AI_SEARCH=DUMMY_AI_SEARCH_SETTINGS_WITH_EMPTY_REGION)
    def test_search_with_fine_grained_auth(self):
        with patch.object(OpenSearch, '__init__', self.nop):
            with patch.object(SentenceTransformer, '__init__', self.nop):
                reload(search)
                self.assertEqual(
                    search.auth,
                    (
                        self.DUMMY_AI_SEARCH_SETTINGS_WITH_EMPTY_REGION['KEY'],
                        self.DUMMY_AI_SEARCH_SETTINGS_WITH_EMPTY_REGION['SECRET'],
                    ),
                )

    @override_settings(ANSIBLE_AI_SEARCH=DUMMY_AI_SEARCH_SETTINGS)
    @patch('boto3.Session.get_credentials')
    @patch('boto3.Session.__init__', return_value=None)
    def test_search_with_signature_auth(self, Session, get_credentials):
        with patch.object(OpenSearch, '__init__', self.nop):
            with patch.object(SentenceTransformer, '__init__', self.nop):
                get_credentials.return_value = 'creds'
                reload(search)
                Session.assert_called_once_with(
                    aws_access_key_id=self.DUMMY_AI_SEARCH_SETTINGS['KEY'],
                    aws_secret_access_key=self.DUMMY_AI_SEARCH_SETTINGS['SECRET'],
                )
                self.assertIsInstance(search.auth, AWSV4SignerAuth)
                self.assertEqual(search.auth.credentials, get_credentials.return_value)
                self.assertEqual(search.auth.region, self.DUMMY_AI_SEARCH_SETTINGS['REGION'])
                self.assertEqual(search.auth.service, 'es')
