from rest_framework import serializers


class WCAKeySerializer(serializers.Serializer):
    key = serializers.CharField()
    description = serializers.CharField()


class WCAKeysSerializer(serializers.Serializer):
    class Meta:
        fields = ['keys']

    keys = serializers.ListField(child=WCAKeySerializer())
