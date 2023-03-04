import imp
import logging
import pickle

import grpc
from django.conf import settings
from rest_framework.response import Response

import base
from grpc_pb import (
    common_service_pb2,
    common_service_pb2_grpc,
)

logger = logging.getLogger(__name__)


class GrpcClient(base.ModelMeshClient):
    def __init__(self, inference_url, management_url):
        super().__init__(inference_url=inference_url, management_url=management_url)
        self._inference_stub = self.get_inference_stub()

    def get_inference_stub(self) -> common_service_pb2_grpc.WisdomExtServiceStub:
        channel = grpc.insecure_channel(self._inference_url)
        logger.debug("Inference URL: " + self._inference_url)
        stub = common_service_pb2_grpc.WisdomExtServiceStub(channel)
        logger.debug("Inference Stub: " + str(stub))
        return stub

    def infer(self, prompt, context) -> Response:
        logger.debug(f"Input prompt: {prompt}")
        logger.debug(f"Input context: {context}")
        response = self._inference_stub.AnsiblePredict(
            request=common_service_pb2.AnsibleRequest(
                prompt=prompt, context=context
            ),
            metadata=[("mm-vmodel-id", "gpu-version-inference-service")],
        )

        try:
            # TODO(rg): remove these debug statements
            print(type(response))
            print(response.label)
            # TODO(rg): this should be formatted properly
            result = { "predictions": [response.label] }
            #result = response.prediction.decode('utf-8')
            return Response(result, status=200)
        except grpc.RpcError as exc:
            return Response(exc.details(), status=400)
