# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: classification-types.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import builder as _builder
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from . import producer_types_pb2 as producer__types__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1a\x63lassification-types.proto\x12\x1awatson_core_data_model.nlp\x1a\x14producer-types.proto\"3\n\tClassInfo\x12\x12\n\nclass_name\x18\x01 \x01(\t\x12\x12\n\nconfidence\x18\x02 \x01(\x02\"\x92\x01\n\x18\x43lassificationPrediction\x12\x36\n\x07\x63lasses\x18\x01 \x03(\x0b\x32%.watson_core_data_model.nlp.ClassInfo\x12>\n\x0bproducer_id\x18\x02 \x01(\x0b\x32).watson_core_data_model.common.ProducerId\"P\n\x19\x43lassificationTrainRecord\x12\x0c\n\x04text\x18\x01 \x01(\t\x12\x0e\n\x06labels\x18\x02 \x03(\t\x12\x15\n\rlanguage_code\x18\x03 \x01(\t*0\n\tModelType\x12\x10\n\x0cMULTI_TARGET\x10\x00\x12\x11\n\rSINGLE_TARGET\x10\x01\x42\x64\n\x17\x63om.ibm.watson.runtime.P\x01ZGgithub.ibm.com/ai-foundation/_runtime_client/watson_core_data_model/nlpb\x06proto3')

_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'classification_types_pb2', globals())
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  DESCRIPTOR._serialized_options = b'\n\027com.ibm.watson.runtime.P\001ZGgithub.ibm.com/ai-foundation/_runtime_client/watson_core_data_model/nlp'
  _MODELTYPE._serialized_start=364
  _MODELTYPE._serialized_end=412
  _CLASSINFO._serialized_start=80
  _CLASSINFO._serialized_end=131
  _CLASSIFICATIONPREDICTION._serialized_start=134
  _CLASSIFICATIONPREDICTION._serialized_end=280
  _CLASSIFICATIONTRAINRECORD._serialized_start=282
  _CLASSIFICATIONTRAINRECORD._serialized_end=362
# @@protoc_insertion_point(module_scope)
