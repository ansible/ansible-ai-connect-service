import json
import logging
import secrets
import time
from typing import Optional

import requests
from django.conf import settings

from .base import ModelMeshClient

logger = logging.getLogger(__name__)


class DummyClient(ModelMeshClient):
    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)
        self.session = requests.Session()
        self.headers = {"Content-Type": "application/json"}

    def infer(self, model_input, model_id=None, suggestion_id=None):
        logger.debug("!!!! settings.ANSIBLE_AI_MODEL_MESH_API_TYPE == 'dummy' !!!!")
        logger.debug("!!!! Mocking Model response !!!!")
        if settings.DUMMY_MODEL_RESPONSE_LATENCY_USE_JITTER:
            jitter: float = secrets.randbelow(1000) * 0.001
        else:
            jitter: float = 0.001
        time.sleep(settings.DUMMY_MODEL_RESPONSE_MAX_LATENCY_MSEC * jitter)
        response_body = json.loads(settings.DUMMY_MODEL_RESPONSE_BODY)
        response_body['model_id'] = '_'
        return response_body

    def get_model_id(
        self,
        organization_id: Optional[int] = None,
        requested_model_id: str = '',
    ) -> str:
        return requested_model_id or settings.ANSIBLE_AI_MODEL_NAME
