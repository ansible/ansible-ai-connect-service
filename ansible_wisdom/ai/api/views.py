# Create your views here.
import logging

from django.apps import apps
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .data.data_model import APIPayload
from .data.data_model import ModelMeshPayload

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)


class CompletionsUserRateThrottle(UserRateThrottle):
    rate = '10/minute'


class Completions(APIView):
    throttle_classes = [CompletionsUserRateThrottle]

    def post(self, request) -> Response:
        model_mesh_client = apps.get_app_config("ai").model_mesh_client
        payload = APIPayload(**request.data)
        model_name = payload.model_name
        model_mesh_payload = ModelMeshPayload(
            instances=[{"prompt": payload.prompt, "context": payload.context}]
        )
        data = model_mesh_payload.dict()
        logger.debug(f"Input to inference: {data}")
        response = model_mesh_client.infer(data, model_name=model_name)
        logger.debug(f"Response from inference: {response.data}")
        return response
