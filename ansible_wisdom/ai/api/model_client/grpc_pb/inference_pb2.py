# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: inference.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder

# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from google.protobuf import empty_pb2 as google_dot_protobuf_dot_empty__pb2

DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(
    b'\n\x0finference.proto\x12 org.pytorch.serve.grpc.inference\x1a\x1bgoogle/protobuf/empty.proto\"\xbd\x01\n\x12PredictionsRequest\x12\x12\n\nmodel_name\x18\x01 \x01(\t\x12\x15\n\rmodel_version\x18\x02 \x01(\t\x12N\n\x05input\x18\x03 \x03(\x0b\x32?.org.pytorch.serve.grpc.inference.PredictionsRequest.InputEntry\x1a,\n\nInputEntry\x12\x0b\n\x03key\x18\x01 \x01(\t\x12\r\n\x05value\x18\x02 \x01(\x0c:\x02\x38\x01\"(\n\x12PredictionResponse\x12\x12\n\nprediction\x18\x01 \x01(\x0c\"*\n\x18TorchServeHealthResponse\x12\x0e\n\x06health\x18\x01 \x01(\t2\xf1\x01\n\x14InferenceAPIsService\x12\\\n\x04Ping\x12\x16.google.protobuf.Empty\x1a:.org.pytorch.serve.grpc.inference.TorchServeHealthResponse\"\x00\x12{\n\x0bPredictions\x12\x34.org.pytorch.serve.grpc.inference.PredictionsRequest\x1a\x34.org.pytorch.serve.grpc.inference.PredictionResponse\"\x00\x42\x02P\x01\x62\x06proto3'
)

_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'inference_pb2', globals())
if _descriptor._USE_C_DESCRIPTORS == False:
    DESCRIPTOR._options = None
    DESCRIPTOR._serialized_options = b'P\001'
    _PREDICTIONSREQUEST_INPUTENTRY._options = None
    _PREDICTIONSREQUEST_INPUTENTRY._serialized_options = b'8\001'
    _PREDICTIONSREQUEST._serialized_start = 83
    _PREDICTIONSREQUEST._serialized_end = 272
    _PREDICTIONSREQUEST_INPUTENTRY._serialized_start = 228
    _PREDICTIONSREQUEST_INPUTENTRY._serialized_end = 272
    _PREDICTIONRESPONSE._serialized_start = 274
    _PREDICTIONRESPONSE._serialized_end = 314
    _TORCHSERVEHEALTHRESPONSE._serialized_start = 316
    _TORCHSERVEHEALTHRESPONSE._serialized_end = 358
    _INFERENCEAPISSERVICE._serialized_start = 361
    _INFERENCEAPISSERVICE._serialized_end = 602
# @@protoc_insertion_point(module_scope)
