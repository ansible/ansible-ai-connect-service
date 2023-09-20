import logging

import grpc
from django.conf import settings

from .base import ModelMeshClient
from .exceptions import ModelTimeoutError
from .grpc_pb import ansiblerequest_pb2, wisdomextservice_pb2_grpc

logger = logging.getLogger(__name__)


class GrpcClient(ModelMeshClient):
    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)
        self._inference_stub = self.get_inference_stub()

    def get_inference_stub(self) -> wisdomextservice_pb2_grpc.WisdomExtServiceStub:
        logger.debug("Inference URL: " + self._inference_url)
        channel = grpc.insecure_channel(self._inference_url)
        stub = wisdomextservice_pb2_grpc.WisdomExtServiceStub(channel)
        logger.debug("Inference Stub: " + str(stub))
        return stub

    def set_inference_url(self, inference_url):
        super().set_inference_url(inference_url=inference_url)
        self._inference_stub = self.get_inference_stub()

    def infer(self, data, model_name):
        model_name = model_name or settings.ANSIBLE_AI_MODEL_NAME
        logger.debug(f"Input prompt: {data}")
        prompt = data.get("instances", [{}])[0].get("prompt", "")
        context = data.get("instances", [{}])[0].get("context", "")
        logger.debug(f"Input prompt: {prompt}")
        logger.debug(f"Input context: {context}")

        try:
            response = self._inference_stub.AnsiblePredict(
                request=ansiblerequest_pb2.AnsibleRequest(prompt=prompt, context=context),
                metadata=[("mm-vmodel-id", model_name)],
                timeout=self.timeout,
            )

            logger.debug(f"inference response: {response}")
            logger.debug(f"inference response: {response.text}")
            result = {"predictions": [response.text]}
            result['model_id'] = model_name
            return result
        except grpc.RpcError as exc:
            if exc.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                raise ModelTimeoutError
            else:
                logger.error(f"gRPC client error: {exc.details()}")
                raise
