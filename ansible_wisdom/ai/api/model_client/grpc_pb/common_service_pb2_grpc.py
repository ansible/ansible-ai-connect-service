# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc

from . import common_service_pb2 as common__service__pb2
from . import generation_pb2 as generation__pb2


class WisdomExtServiceStub(object):
    """Missing associated documentation comment in .proto file."""

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.AnsiblePredict = channel.unary_unary(
                '/watson.runtime.wisdom_ext.v0.WisdomExtService/AnsiblePredict',
                request_serializer=common__service__pb2.AnsibleRequest.SerializeToString,
                response_deserializer=generation__pb2.GeneratedResult.FromString,
                )


class WisdomExtServiceServicer(object):
    """Missing associated documentation comment in .proto file."""

    def AnsiblePredict(self, request, context):
        """*

        This rpc supports 1 Modules: ['AnsibleCodegen']



        AnsibleCodegen docstring:

        ----------------------------

        Run hugging face text generation using prompt and input context



        Args:

        prompt: str

        Prompt for task to be performed

        context: str

        The input context

        Returns:

        GeneratedResult

        ----------------------------


        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_WisdomExtServiceServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'AnsiblePredict': grpc.unary_unary_rpc_method_handler(
                    servicer.AnsiblePredict,
                    request_deserializer=common__service__pb2.AnsibleRequest.FromString,
                    response_serializer=generation__pb2.GeneratedResult.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'watson.runtime.wisdom_ext.v0.WisdomExtService', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


 # This class is part of an EXPERIMENTAL API.
class WisdomExtService(object):
    """Missing associated documentation comment in .proto file."""

    @staticmethod
    def AnsiblePredict(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/watson.runtime.wisdom_ext.v0.WisdomExtService/AnsiblePredict',
            common__service__pb2.AnsibleRequest.SerializeToString,
            generation__pb2.GeneratedResult.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)
