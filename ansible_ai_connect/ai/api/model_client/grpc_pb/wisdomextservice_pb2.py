# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: wisdomextservice.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder

# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from . import ansiblerequest_pb2 as ansiblerequest__pb2
from . import generatedresult_pb2 as generatedresult__pb2

DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(
    b"\n\x16wisdomextservice.proto\x12\x18\x63\x61ikit.runtime.WisdomExt\x1a\x14\x61nsiblerequest.proto\x1a\x15generatedresult.proto2v\n\x10WisdomExtService\x12\x62\n\x0e\x41nsiblePredict\x12(.caikit.runtime.WisdomExt.AnsibleRequest\x1a&.caikit_data_model.ext.GeneratedResultb\x06proto3"
)

_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, "wisdomextservice_pb2", globals())
if _descriptor._USE_C_DESCRIPTORS == False:
    DESCRIPTOR._options = None
    _WISDOMEXTSERVICE._serialized_start = 97
    _WISDOMEXTSERVICE._serialized_end = 215
# @@protoc_insertion_point(module_scope)