"""
DRF Serializer classes for input/output validations and OpenAPI document generation.
"""
import re
import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import (
    OpenApiExample,
    extend_schema_field,
    extend_schema_serializer,
)
from rest_framework import serializers

from .fields import AnonymizedCharField


class Metadata(serializers.Serializer):
    class Meta:
        fields = ['documentUri', 'activityId']

    documentUri = AnonymizedCharField(required=False)
    activityId = serializers.UUIDField(
        format='hex_verbose',
        required=False,
        label="Activity ID",
        help_text="A UUID that identifies a user activity session within a given document.",
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

    prompt = AnonymizedCharField(
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
        # If suggestion ID was not included in the request, set a random UUID to it.
        if data.get('suggestionId') is None:
            data['suggestionId'] = uuid.uuid4()
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
    documentUri = AnonymizedCharField(required=False)
    action = serializers.ChoiceField(choices=USER_ACTION_CHOICES)
    error = AnonymizedCharField(required=False)
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
        help_text="A UUID that identifies a user activity session to the document uploaded.",
    )


class AnsibleContentFeedback(serializers.Serializer):
    CONTENT_UPLOAD_TRIGGER = (('0', 'FILE_OPEN'), ('1', 'FILE_CLOSE'), ('2', 'TAB_CHANGE'))

    class Meta:
        fields = ['content', 'documentUri', 'trigger', 'activityId']

    content = AnonymizedCharField(
        trim_whitespace=False,
        required=True,
        label='Ansible Content',
        help_text='Ansible file content.',
    )
    documentUri = AnonymizedCharField()
    trigger = serializers.ChoiceField(choices=CONTENT_UPLOAD_TRIGGER)
    activityId = serializers.UUIDField(
        format='hex_verbose',
        required=False,
        label="Activity ID",
        help_text="A UUID that identifies a user activity session to the document uploaded.",
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


class AttributionRequestSerializer(serializers.Serializer):
    class Meta:
        fields = ['suggestion', 'suggestionId']

    suggestion = serializers.CharField(trim_whitespace=False)
    suggestionId = serializers.UUIDField(
        format='hex_verbose',
        required=False,
        label="Suggestion ID",
        help_text=(
            "A UUID that identifies the particular suggestion"
            " attribution data is being requested for."
        ),
    )


class DataSource(models.IntegerChoices):
    UNKNOWN = -1, "Unknown Source"
    GALAXY = 0, "Ansible Galaxy"


class AnsibleType(models.IntegerChoices):
    UNKNOWN = -1, "Unknown Ansible Type"
    TASK = 0, "Task"
    PLAYBOOK = 1, "Playbook"


@extend_schema_field(str)
class EnumField(serializers.Field):
    default_error_messages = {'invalid_choice': _('"{input}" is not a valid choice.')}

    def __init__(self, choices, **kwargs):
        self.choices = choices
        self.allow_blank = kwargs.pop('allow_blank', False)

        super().__init__(**kwargs)

    def to_internal_value(self, data):
        try:
            return self.choices(self.choices._member_type_(data))
        except ValueError:
            pass

        try:
            return self.choices['UNKNOWN']
        except KeyError:
            self.fail('invalid_choice', input=data)

    def to_representation(self, value):
        return value.label


class AttributionSerializer(serializers.Serializer):
    repo_name = serializers.CharField()
    repo_url = serializers.URLField()
    path = serializers.CharField()
    license = serializers.CharField()
    data_source = EnumField(choices=DataSource)
    ansible_type = EnumField(choices=AnsibleType)
    score = serializers.FloatField()


class AttributionResponseSerializer(serializers.Serializer):
    class Meta:
        fields = ['attributions']

    attributions = serializers.ListField(child=AttributionSerializer())
