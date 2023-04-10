from ansible_anonymizer import anonymizer
from rest_framework import serializers


class AnonymizedFieldMixin:
    def to_internal_value(self, data):
        data = super().to_internal_value(data)
        data = anonymizer.anonymize_struct(data)
        return data


class AnonymizedCharField(AnonymizedFieldMixin, serializers.CharField):
    pass
