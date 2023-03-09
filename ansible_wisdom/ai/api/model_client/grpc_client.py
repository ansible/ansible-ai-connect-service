import imp
import logging
import pickle
from urllib.parse import urlparse

import grpc
from django.conf import settings
from .grpc_pb import common_service_pb2, common_service_pb2_grpc
from rest_framework.response import Response

from .base import ModelMeshClient

logger = logging.getLogger(__name__)


class GrpcClient(ModelMeshClient):
    def __init__(self, inference_url, management_url):
        super().__init__(inference_url=inference_url, management_url=management_url)
        self._inference_stub = self.get_inference_stub()

    def get_inference_stub(self) -> common_service_pb2_grpc.WisdomExtServiceStub:
        inference_host = urlparse(self._inference_url).netloc
        channel = grpc.insecure_channel(inference_host)
        logger.debug("Inference URL: " + self._inference_url)
        logger.debug("Inference host: " + inference_host)
        stub = common_service_pb2_grpc.WisdomExtServiceStub(channel)
        logger.debug("Inference Stub: " + str(stub))
        return stub

    def infer(self, data, model_name) -> Response:
        logger.debug(f"Input prompt: {data}")
        prompt = data["instances"][0]["prompt"]
        context = data["instances"][0]["context"]
        logger.debug(f"Input prompt: {prompt}")
        logger.debug(f"Input context: {context}")
        response = self._inference_stub.AnsiblePredict(
            request=common_service_pb2.AnsibleRequest(prompt=prompt, context=context),
            metadata=[("mm-vmodel-id", model_name)],
        )

        try:
            logger.debug(f"inference response: {response}")
            # TODO(rg): ensure this is formatted properly
            logger.debug(f"inference response: {response.text}")
            result = {"predictions": [response.text]}
            # result = response.prediction.decode('utf-8')
            return Response(result, status=200)
        except grpc.RpcError as exc:
            return Response(exc.details(), status=400)
