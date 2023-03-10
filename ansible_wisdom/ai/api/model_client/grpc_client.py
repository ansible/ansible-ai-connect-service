import json
import logging

import grpc
from django.conf import settings
from rest_framework.response import Response

from .base import ModelMeshClient
from .grpc_pb import common_service_pb2, common_service_pb2_grpc

logger = logging.getLogger(__name__)


class GrpcClient(ModelMeshClient):
    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)
        self._inference_stub = self.get_inference_stub()

    def get_inference_stub(self) -> common_service_pb2_grpc.WisdomExtServiceStub:
        logger.debug("Inference URL: " + self._inference_url)
        channel = grpc.insecure_channel(self._inference_url)
        stub = common_service_pb2_grpc.WisdomExtServiceStub(channel)
        logger.debug("Inference Stub: " + str(stub))
        return stub

    def infer(self, data, model_name) -> Response:
        logger.debug(f"Input prompt: {data}")
        prompt = data.get("instances", [{}])[0].get("prompt", "")
        context = data.get("instances", [{}])[0].get("context", "")
        logger.debug(f"Input prompt: {prompt}")
        logger.debug(f"Input context: {context}")

        try:
            response = self._inference_stub.AnsiblePredict(
                request=common_service_pb2.AnsibleRequest(prompt=prompt, context=context),
                metadata=[("mm-vmodel-id", model_name)],
            )

            logger.debug(f"inference response: {response}")
            logger.debug(f"inference response: {response.text}")
            result = {"predictions": [response.text]}
            return Response(json.dumps(result), status=200)
        except grpc.RpcError as exc:
            logger.error(f"gRPC client error: {exc.details()}")
            return Response("Invalid request", status=400)
        except Exception as exc:
            logger.error(f"gRPC client error: {exc.details()}")
            return Response("Malformed response from server", status=500)
