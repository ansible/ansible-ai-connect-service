import base64
import io

import numpy as np
from django.conf import settings
from rest_framework.test import APITestCase
from sentence_transformers import SentenceTransformer

from ..backends import PRE_DEFINED_SEARCH_STRING, PRE_ENCODED_QUERY


class TestSearchWithPreEncoded(APITestCase):
    def test_pre_encoded_search_string(self):
        model = SentenceTransformer(f"sentence-transformers/{settings.ANSIBLE_AI_SEARCH['MODEL']}")
        encoded = model.encode(sentences=PRE_DEFINED_SEARCH_STRING, batch_size=16)

        #
        # Uncomment following lines to generate PRE_ENCODED_QUERY:
        #
        # def chunkstring(string, length):
        #     return (string[0 + i:length + i] for i in range(0, len(string), length))
        #
        # f = io.BytesIO()
        # np.save(f, encoded)
        # serialized = f.getvalue()
        # b64encoded = base64.b64encode(serialized).decode('latin-1')
        # for chunk in chunkstring(b64encoded, 100):
        #     print(chunk)

        decoded = base64.b64decode(PRE_ENCODED_QUERY)
        f = io.BytesIO(decoded)
        loaded = np.load(f)

        self.assertTrue(np.array_equal(encoded, loaded))
