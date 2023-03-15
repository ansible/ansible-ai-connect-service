"""
DRF Serializer classes for input/output validations and OpenAPI document generation.
"""
import re

from drf_spectacular.utils import OpenApiExample, extend_schema_serializer
from rest_framework import serializers


class Metadata(serializers.Serializer):
    class Meta:
        fields = ['documentUri', 'activityId']

    documentUri = serializers.CharField(required=False)
    activityId = serializers.UUIDField(
        format='hex_verbose',
        required=False,
        label="Activity ID",
        help_text="A UUID that identifies a user activity " "session within a given document.",
    )


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
        fields = ['prompt', 'suggestionId', 'metadata']

    prompt = serializers.CharField(
        trim_whitespace=False,
        required=True,
        label='Prompt',
        help_text='Editor prompt.',
    )
    suggestionId = serializers.UUIDField(
        format='hex_verbose',
        required=False,
        label="Suggestion ID",
        help_text="A UUID that identifies a suggestion.",
    )
    metadata = Metadata(required=False)

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

        # Confirm the prompt contains some flavor of '- name:'
        match = re.search(r"^[\s]*-[\s]+name[\s]*:", extracted_prompt)
        if not match:
            raise serializers.ValidationError("prompt does not contain the name parameter")

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


class InlineSuggestionFeedback(serializers.Serializer):
    USER_ACTION_CHOICES = (('0', 'ACCEPT'), ('1', 'IGNORE'))

    class Meta:
        fields = [
            'latency',
            'userActionTime',
            'documentUri',
            'action',
            'error',
            'suggestionId',
            'activityId',
        ]

    latency = serializers.FloatField(required=False)
    userActionTime = serializers.FloatField(required=False)
    documentUri = serializers.CharField(required=False)
    action = serializers.ChoiceField(choices=USER_ACTION_CHOICES)
    error = serializers.CharField(required=False)
    suggestionId = serializers.UUIDField(
        format='hex_verbose',
        required=True,
        label="Suggestion ID",
        help_text="A UUID that identifies a suggestion.",
    )
    activityId = serializers.UUIDField(
        format='hex_verbose',
        required=False,
        label="Activity ID",
        help_text="A UUID that identifies a user activity " "session to the document uploaded.",
    )


class AnsibleContentFeedback(serializers.Serializer):
    CONTENT_UPLOAD_TRIGGER = (('0', 'FILE_OPEN'), ('1', 'FILE_CLOSE'), ('2', 'TAB_CHANGE'))

    class Meta:
        fields = ['content', 'documentUri', 'trigger', 'activityId']

    content = serializers.CharField(
        trim_whitespace=False,
        required=True,
        label='Ansible Content',
        help_text='Ansible file content.',
    )
    documentUri = serializers.CharField()
    trigger = serializers.ChoiceField(choices=CONTENT_UPLOAD_TRIGGER)
    activityId = serializers.UUIDField(
        format='hex_verbose',
        required=False,
        label="Activity ID",
        help_text="A UUID that identifies a user activity " "session to the document uploaded.",
    )


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Valid inline suggestion feedback example',
            summary='Feedback Request sample for inline suggestion '
            'to identify if the suggestion is accepted or ignored.',
            description='A valid inline suggestion feedback sample '
            'request to get details about the suggestion like latency time, '
            'user decision time, user action and suggestion id.',
            value={
                "inlineSuggestion": {
                    "latency": 1000,
                    "userActionTime": 5155,
                    "action": "0",
                    "suggestionId": "a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6",
                }
            },
            request_only=True,
            response_only=False,
        ),
        OpenApiExample(
            'Valid ansible content feedback example',
            summary='Feedback Request sample for Ansible content upload',
            description='A valid sample request to get ansible content as feedback.',
            value={
                "ansibleContent": {
                    "content": "---\n- hosts: all\n  become: yes\n\n  "
                    "tasks:\n  - name: Install ssh\n",
                    "documentUri": "file:///home/user/ansible/test.yaml",
                    "trigger": "0",
                }
            },
            request_only=True,
            response_only=False,
        ),
    ]
)
class FeedbackRequestSerializer(serializers.Serializer):
    class Meta:
        fields = ['inlineSuggestion', 'ansibleContent']

    inlineSuggestion = InlineSuggestionFeedback(required=False)
    ansibleContent = AnsibleContentFeedback(required=False)
