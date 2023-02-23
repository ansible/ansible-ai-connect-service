import imp
import logging
import pickle

import grpc
from django.conf import settings
from rest_framework.response import Response

from .base import ModelMeshClient
from .grpc_pb import (
    common_service_pb2,
    common_service_pb2_grpc,
    data_model_pb2,
    inference_pb2,
    inference_pb2_grpc,
    management_pb2,
    management_pb2_grpc,
)

logger = logging.getLogger(__name__)


class GrpcClient(ModelMeshClient):
    def __init__(self, inference_url, management_url):
        super().__init__(inference_url=inference_url, management_url=management_url)
        self._inference_stub = self.get_inference_stub()
        self._management_stub = self.get_management_stub()

    def get_inference_stub(self) -> common_service_pb2_grpc.CoreAnsibleWisdomExtServiceStub:
        channel = grpc.insecure_channel(self._inference_url)
        logger.debug("Inference URL: " + self._inference_url)
        stub = common_service_pb2_grpc.CoreAnsibleWisdomExtServiceStub(channel)
        logger.debug("Inference Stub: " + str(stub))
        return stub

    def infer(self, prompt, context) -> Response:
        logger.debug(f"Input prompt: {prompt}")
        logger.debug(f"Input context: {context}")
        response = self._inference_stub.AnsibleWisdomPredict(
            common_service_pb2.AnsibleWisdomRequest(
                prompt=prompt, input=data_model_pb2.RawDocument(text=context)
            ),
            metadata=(("mm-vmodel-id", "gpu-version-inference-service-v01")),
        )

        try:
            result = response.prediction.decode('utf-8')
            return Response(result, status=200)
        except grpc.RpcError as exc:
            return Response(exc.details(), status=400)
