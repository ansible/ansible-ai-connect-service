# Create your views here.
import logging

from datetime import datetime, timedelta

from django.apps import apps
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .data.data_model import APIPayload, ModelMeshPayload

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)


def rate_limit(session, duration=10):
    last_call = datetime.fromisoformat(session.get('last_call', "1970-01-01"))
    session['last_call'] = datetime.now().isoformat()
    return last_call > datetime.now() - timedelta(seconds=duration)


class Completions(APIView):
    def post(self, request) -> Response:
        if rate_limit(request.session):
            return Response("429 Too Many Requests", status=status.HTTP_429_TOO_MANY_REQUESTS)

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
