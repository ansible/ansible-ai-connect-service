import logging

import grpc
from django.conf import settings
from rest_framework.response import Response

from ..utils.jaeger import trace, tracer
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

    def infer(self, data, span_ctx, model_name):
        print('INSIDE INFER METHOD')
        inner_span_ctx = None
        if settings.ENABLE_DISTRIBUTED_TRACING:
            with tracer.start_as_current_span(
                'inference through gRPC client', context=span_ctx
            ) as innerSpan:
                try:
                    innerSpan.set_attribute('Class', __class__.__name__)
                except NameError:
                    innerSpan.set_attribute('Class', "none")
                innerSpan.set_attribute('Method', "infer")
                innerSpan.set_attribute('file', __file__)
                innerSpan.set_attribute(
                    'Description',
                    'Responsible for obtaining prediction based on context and prompt',
                )
                inner_span_ctx = trace.set_span_in_context(trace.get_current_span())
        logger.debug(f"Input prompt: {data}")
        prompt = data.get("instances", [{}])[0].get("prompt", "")
        context = data.get("instances", [{}])[0].get("context", "")
        logger.debug(f"Input prompt: {prompt}")
        logger.debug(f"Input context: {context}")

        try:
            if settings.ENABLE_DISTRIBUTED_TRACING:
                with tracer.start_as_current_span(
                    'initializing "response" - ansible prediction', context=inner_span_ctx
                ) as innerSpan:
                    try:
                        innerSpan.set_attribute('Class', __class__.__name__)
                    except NameError:
                        innerSpan.set_attribute('Class', "none")
                    innerSpan.set_attribute('Method', "AnsiblePredict")
                    innerSpan.set_attribute('file', __file__)
                    innerSpan.set_attribute(
                        'Description',
                        'Initializes response and calls AnsibleRequest '
                        'method with parameters "prompt" and "context"',
                    )
            response = self._inference_stub.AnsiblePredict(
                request=ansiblerequest_pb2.AnsibleRequest(prompt=prompt, context=context),
                metadata=[("mm-vmodel-id", model_name)],
                timeout=self.timeout,
            )

            logger.debug(f"inference response: {response}")
            logger.debug(f"inference response: {response.text}")
            result = {"predictions": [response.text]}
            return result
        except grpc.RpcError as exc:
            if exc.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                raise ModelTimeoutError
            else:
                logger.error(f"gRPC client error: {exc.details()}")
                raise
