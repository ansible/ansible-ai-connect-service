from copy import copy
from unittest.mock import patch

import numpy as np
from ai.search import initialize_OpenSearch, search
from django.test import override_settings
from opensearchpy import OpenSearch
from rest_framework.test import APITestCase
from sentence_transformers import SentenceTransformer


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
        def encode(self, input):
            return input

    @override_settings(ANSIBLE_AI_SEARCH=DUMMY_AI_SEARCH_SETTINGS)
    def test_initialize_OpenSearch(self):
        with patch.object(OpenSearch, '__init__', self.nop):
            with patch.object(SentenceTransformer, '__init__', self.nop):
                client, model = initialize_OpenSearch()
                self.assertIsNotNone(client)
                self.assertIsNotNone(model)

        with patch('ai.search.client', self.DummyClient()):
            with patch('ai.search.model', self.DummySentenceTransformer()):
                ret = search(np.array(1))
                self.assertIsNotNone(ret)

    @override_settings(ANSIBLE_AI_SEARCH=DUMMY_AI_SEARCH_SETTINGS_WITH_EMPTY_HOST)
    def test_skip_initializing_OpenSearch(self):
        with patch.object(OpenSearch, '__init__', self.nop):
            with patch.object(SentenceTransformer, '__init__', self.nop):
                client, model = initialize_OpenSearch()
                self.assertIsNone(client)
                self.assertIsNone(model)

    def test_search(self):
        with patch('ai.search.client', self.DummyClient()):
            with patch('ai.search.model', self.DummySentenceTransformer()):
                ret = search(np.array(1))
                self.assertIsNotNone(ret)

    def test_search_with_none_client(self):
        with patch('ai.search.client', None):
            with self.assertRaises(Exception):
                ret = search(np.array(1))
