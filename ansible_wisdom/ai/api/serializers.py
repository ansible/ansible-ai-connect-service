"""
DRF Serializer classes for input/output validations and OpenAPI document generation.
"""
from drf_spectacular.utils import OpenApiExample, extend_schema_serializer
from rest_framework import serializers

from .models import CompletionRequest, CompletionResponse


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Valid example',
            summary='Request Sample',
            description='A valid sample request.',
            value={
                'context': '---\n- hosts: all\n  become: yes\n\n  tasks:\n',
                'prompt': '- name: Install Apache\n',
            },
            request_only=True,
            response_only=False,
        ),
    ]
)
class CompletionRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompletionRequest
        fields = ['context', 'prompt', 'userId', 'suggestionId']

    context = serializers.CharField(
        trim_whitespace=False,
        label='Context',
        help_text='Editor context. This is required.',
    )
    prompt = serializers.CharField(
        trim_whitespace=False,
        required=False,
        label='Prompt',
        help_text='Editor prompt.',
    )
    userId = serializers.UUIDField(
        format='hex_verbose',
        required=False,
        label="User ID",
        help_text="A UUID that identifies a user.",
    )
    suggestionId = serializers.UUIDField(
        format='hex_verbose',
        required=False,
        label="Suggestion ID",
        help_text="A UUID that identifies a suggestion.",
    )


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Valid example',
            summary='Response sample',
            description='A valid sample response.',
            value={'predictions': ['  package:\n    name: apache2\n    state: present\n']},
            request_only=False,
            response_only=True,
        ),
    ]
)
class CompletionResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompletionResponse
        fields = ['predictions']

    predictions = serializers.ListField(child=serializers.CharField(trim_whitespace=False))
