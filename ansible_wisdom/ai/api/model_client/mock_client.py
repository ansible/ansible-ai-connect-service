import json
import logging
import random
import time

import requests
from django.conf import settings
from rest_framework.response import Response

from .base import ModelMeshClient

logger = logging.getLogger(__name__)


class MockClient(ModelMeshClient):
    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)
        self.session = requests.Session()
        self.headers = {"Content-Type": "application/json"}

    def infer(self, model_input, model_name="wisdom"):
        logger.debug("!!!! settings.ANSIBLE_AI_MODEL_MESH_API_TYPE == 'mock' !!!!")
        logger.debug("!!!! Mocking Model response !!!!")
        jitter = random.random() if settings.MOCK_MODEL_RESPONSE_LATENCY_USE_JITTER else 1
        time.sleep((settings.MOCK_MODEL_RESPONSE_MAX_LATENCY_MSEC * jitter) / 1000)
        return json.loads(settings.MOCK_MODEL_RESPONSE_BODY)
