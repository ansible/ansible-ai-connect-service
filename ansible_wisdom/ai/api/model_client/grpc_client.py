import imp
import logging
import pickle

import grpc
from django.conf import settings
from rest_framework.response import Response

from .base import ModelMeshClient
from .grpc_pb import (
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

    def get_inference_stub(self) -> inference_pb2_grpc.InferenceAPIsServiceStub:
        channel = grpc.insecure_channel(self._inference_url)
        logger.debug("Inference URL: " + self._inference_url)
        stub = inference_pb2_grpc.InferenceAPIsServiceStub(channel)
        logger.debug("Inference Stub: " + str(stub))
        return stub

    def get_management_stub(self) -> management_pb2_grpc.ManagementAPIsServiceStub:
        channel = grpc.insecure_channel(self._management_url)
        stub = management_pb2_grpc.ManagementAPIsServiceStub(channel)
        return stub

    def infer(self, model_input, model_name="wisdom") -> Response:
        input_data = {'data': pickle.dumps(model_input)}
        logger.debug(f"Input Data: {input_data}")
        logger.debug(f"Model Name: {model_name}")
        response = self._inference_stub.Predictions(
            inference_pb2.PredictionsRequest(model_name=model_name, input=input_data)
        )

        try:
            result = response.prediction.decode('utf-8')
            return Response(result, status=200)
        except grpc.RpcError as exc:
            return Response(exc.details(), status=400)
