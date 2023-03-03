# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: rules-types.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import builder as _builder
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from . import producer_types_pb2 as producer__types__pb2
from . import text_primitive_types_pb2 as text__primitive__types__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x11rules-types.proto\x12\x1awatson_core_data_model.nlp\x1a\x14producer-types.proto\x1a\x1atext-primitive-types.proto\"\x82\x01\n\x0fRulesPrediction\x12/\n\x05views\x18\x01 \x03(\x0b\x32 .watson_core_data_model.nlp.View\x12>\n\x0bproducer_id\x18\x02 \x01(\x0b\x32).watson_core_data_model.common.ProducerId\"R\n\x04View\x12\x0c\n\x04name\x18\x01 \x01(\t\x12<\n\nproperties\x18\x02 \x03(\x0b\x32(.watson_core_data_model.nlp.ViewProperty\"\xc2\x01\n\x0cViewProperty\x12O\n\x0c\x61ql_property\x18\x01 \x03(\x0b\x32\x39.watson_core_data_model.nlp.ViewProperty.AqlPropertyEntry\x1a\x61\n\x10\x41qlPropertyEntry\x12\x0b\n\x03key\x18\x01 \x01(\t\x12<\n\x05value\x18\x02 \x01(\x0b\x32-.watson_core_data_model.nlp.ViewPropertyValue:\x02\x38\x01\"\x9b\x04\n\x11ViewPropertyValue\x12\x11\n\x07str_val\x18\x01 \x01(\tH\x00\x12\x13\n\tfloat_val\x18\x02 \x01(\x02H\x00\x12\x11\n\x07int_val\x18\x03 \x01(\x05H\x00\x12\x12\n\x08\x62ool_val\x18\x04 \x01(\x08H\x00\x12\x34\n\x08span_val\x18\x05 \x01(\x0b\x32 .watson_core_data_model.nlp.SpanH\x00\x12H\n\x0clist_str_val\x18\x06 \x01(\x0b\x32\x30.watson_core_data_model.nlp.PropertyListValueStrH\x00\x12L\n\x0elist_float_val\x18\x07 \x01(\x0b\x32\x32.watson_core_data_model.nlp.PropertyListValueFloatH\x00\x12H\n\x0clist_int_val\x18\x08 \x01(\x0b\x32\x30.watson_core_data_model.nlp.PropertyListValueIntH\x00\x12J\n\rlist_bool_val\x18\t \x01(\x0b\x32\x31.watson_core_data_model.nlp.PropertyListValueBoolH\x00\x12J\n\rlist_span_val\x18\n \x01(\x0b\x32\x31.watson_core_data_model.nlp.PropertyListValueSpanH\x00\x42\x07\n\x05value\"#\n\x14PropertyListValueStr\x12\x0b\n\x03val\x18\x01 \x03(\t\"%\n\x16PropertyListValueFloat\x12\x0b\n\x03val\x18\x01 \x03(\x02\"#\n\x14PropertyListValueInt\x12\x0b\n\x03val\x18\x01 \x03(\x05\"$\n\x15PropertyListValueBool\x12\x0b\n\x03val\x18\x01 \x03(\x08\"F\n\x15PropertyListValueSpan\x12-\n\x03val\x18\x01 \x03(\x0b\x32 .watson_core_data_model.nlp.SpanBd\n\x17\x63om.ibm.watson.runtime.P\x01ZGgithub.ibm.com/ai-foundation/_runtime_client/watson_core_data_model/nlpb\x06proto3')

_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'rules_types_pb2', globals())
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  DESCRIPTOR._serialized_options = b'\n\027com.ibm.watson.runtime.P\001ZGgithub.ibm.com/ai-foundation/_runtime_client/watson_core_data_model/nlp'
  _VIEWPROPERTY_AQLPROPERTYENTRY._options = None
  _VIEWPROPERTY_AQLPROPERTYENTRY._serialized_options = b'8\001'
  _RULESPREDICTION._serialized_start=100
  _RULESPREDICTION._serialized_end=230
  _VIEW._serialized_start=232
  _VIEW._serialized_end=314
  _VIEWPROPERTY._serialized_start=317
  _VIEWPROPERTY._serialized_end=511
  _VIEWPROPERTY_AQLPROPERTYENTRY._serialized_start=414
  _VIEWPROPERTY_AQLPROPERTYENTRY._serialized_end=511
  _VIEWPROPERTYVALUE._serialized_start=514
  _VIEWPROPERTYVALUE._serialized_end=1053
  _PROPERTYLISTVALUESTR._serialized_start=1055
  _PROPERTYLISTVALUESTR._serialized_end=1090
  _PROPERTYLISTVALUEFLOAT._serialized_start=1092
  _PROPERTYLISTVALUEFLOAT._serialized_end=1129
  _PROPERTYLISTVALUEINT._serialized_start=1131
  _PROPERTYLISTVALUEINT._serialized_end=1166
  _PROPERTYLISTVALUEBOOL._serialized_start=1168
  _PROPERTYLISTVALUEBOOL._serialized_end=1204
  _PROPERTYLISTVALUESPAN._serialized_start=1206
  _PROPERTYLISTVALUESPAN._serialized_end=1276
# @@protoc_insertion_point(module_scope)
