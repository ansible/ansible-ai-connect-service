# Create your views here.
import logging

from django.apps import apps
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .data.data_model import APIPayload, ModelMeshPayload

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)


class CompletionsUserRateThrottle(UserRateThrottle):
    rate = '10/minute'


class Completions(APIView):
    throttle_classes = [CompletionsUserRateThrottle]

    def post(self, request) -> Response:
        model_mesh_client = apps.get_app_config("ai").model_mesh_client
        logger.debug(f"request payload from client: {request.data}")
        payload = APIPayload(**request.data)
        model_name = payload.model_name
        model_mesh_payload = ModelMeshPayload(
            instances=[{"prompt": payload.prompt, "context": payload.context}]
        )
        data = model_mesh_payload.dict()
        logger.debug(
            f"input to inference for user id {payload.userId} "
            f"and suggestion id {payload.suggestionId}:\n{data}"
        )
        response = model_mesh_client.infer(data, model_name=model_name)
        # TODO do we capture these in segment as well
        logger.debug(
            f"response from inference for user id {payload.userId} "
            f"and suggestion id {payload.suggestionId}:\n{response.data}"
        )
        response.data = self.postprocess(response.data, payload.prompt, payload.context)
        logger.debug(
            f"response from postprocess for user id {payload.userId} "
            f"and suggestion id {payload.suggestionId}:\n{response.data}"
        )
        return response

    def postprocess(self, recommendation, prompt, context):
        ari_caller = apps.get_app_config("ai").ari_caller
        try:
            if self.ari_caller:
                recommendation = ari_caller.postprocess(recommendation, prompt, context)
            else:
                logger.warn('skipped post processing because ari was not initialized')
        except Exception:
            # return the original recommendation if we failed to parse
            logger.exception(
                f'failed to postprocess recommendation with prompt {prompt} '
                f'context {context} and model recommendation {recommendation}'
            )

        return recommendation
