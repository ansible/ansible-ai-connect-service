"""
DRF Serializer classes for input/output validations and OpenAPI document generation.
"""
from drf_spectacular.utils import OpenApiExample, extend_schema_serializer
from rest_framework import serializers


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Valid example',
            summary='Request Sample',
            description='A valid sample request.',
            value={
                'prompt': '---\n- hosts: all\n  become: yes\n\n  tasks:\n  - name: Install ssh\n',
            },
            request_only=True,
            response_only=False,
        ),
    ]
)
class CompletionRequestSerializer(serializers.Serializer):
    class Meta:
        fields = ['prompt', 'userId', 'suggestionId']

    prompt = serializers.CharField(
        trim_whitespace=False,
        required=True,
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

    def validate(self, data):
        data = super().validate(data)
        CompletionRequestSerializer.extract_prompt_and_context(data)
        return data

    @staticmethod
    def extract_prompt_and_context(data):
        #
        # Set the last line as prompt and the rest as context.
        # Note that usually both prompt and context end with '\n'.
        #
        extracted_prompt = ''
        extracted_context = ''
        prompt_in_request = data['prompt']
        if prompt_in_request:
            s = prompt_in_request[:-1].rpartition('\n')
            if s[1] == '\n':
                extracted_prompt = s[2] + prompt_in_request[-1]
                extracted_context = s[0] + s[1]
            else:
                extracted_prompt = prompt_in_request
                extracted_context = ''

        data['prompt'] = extracted_prompt
        data['context'] = extracted_context


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Valid example',
            summary='Response sample',
            description='A valid sample response.',
            value={
                'predictions': [
                    '    ansible.builtin.package:\n      name: openssh-server\n      state: present'
                ]
            },
            request_only=False,
            response_only=True,
        ),
    ]
)
class CompletionResponseSerializer(serializers.Serializer):
    class Meta:
        fields = ['predictions']

    predictions = serializers.ListField(child=serializers.CharField(trim_whitespace=False))
