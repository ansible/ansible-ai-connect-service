# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: nounphrases-types.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import builder as _builder
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from . import producer_types_pb2 as producer__types__pb2
from . import text_primitive_types_pb2 as text__primitive__types__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x17nounphrases-types.proto\x12\x1awatson_core_data_model.nlp\x1a\x14producer-types.proto\x1a\x1atext-primitive-types.proto\"<\n\nNounPhrase\x12.\n\x04span\x18\x01 \x01(\x0b\x32 .watson_core_data_model.nlp.Span\"\x95\x01\n\x15NounPhrasesPrediction\x12<\n\x0cnoun_phrases\x18\x01 \x03(\x0b\x32&.watson_core_data_model.nlp.NounPhrase\x12>\n\x0bproducer_id\x18\x02 \x01(\x0b\x32).watson_core_data_model.common.ProducerIdBd\n\x17\x63om.ibm.watson.runtime.P\x01ZGgithub.ibm.com/ai-foundation/_runtime_client/watson_core_data_model/nlpb\x06proto3')

_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'nounphrases_types_pb2', globals())
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  DESCRIPTOR._serialized_options = b'\n\027com.ibm.watson.runtime.P\001ZGgithub.ibm.com/ai-foundation/_runtime_client/watson_core_data_model/nlp'
  _NOUNPHRASE._serialized_start=105
  _NOUNPHRASE._serialized_end=165
  _NOUNPHRASESPREDICTION._serialized_start=168
  _NOUNPHRASESPREDICTION._serialized_end=317
# @@protoc_insertion_point(module_scope)
