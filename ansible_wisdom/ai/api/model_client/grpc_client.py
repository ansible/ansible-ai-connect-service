import logging

import grpc

from ansible_wisdom.ai.api.formatter import get_task_names_from_prompt

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

    def infer(self, model_input, model_id=None, suggestion_id=None):
        model_id = self.get_model_id(None, model_id)
        logger.debug(f"Input prompt: {model_input}")
        prompt = model_input.get("instances", [{}])[0].get("prompt", "")
        context = model_input.get("instances", [{}])[0].get("context", "")
        logger.debug(f"Input prompt: {prompt}")
        logger.debug(f"Input context: {context}")

        try:
            task_count = len(get_task_names_from_prompt(prompt))
            response = self._inference_stub.AnsiblePredict(
                request=ansiblerequest_pb2.AnsibleRequest(prompt=prompt, context=context),
                metadata=[("mm-vmodel-id", model_id)],
                timeout=self.timeout(task_count),
            )

            logger.debug(f"inference response: {response}")
            logger.debug(f"inference response: {response.text}")
            result = {"predictions": [response.text]}
            result['model_id'] = model_id
            return result
        except grpc.RpcError as exc:
            if exc.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                raise ModelTimeoutError
            else:
                logger.error(f"gRPC client error: {exc.details()}")
                raise
