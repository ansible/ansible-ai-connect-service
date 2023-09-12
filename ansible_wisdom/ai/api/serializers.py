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

from . import formatter as fmtr
from .fields import AnonymizedCharField, AnonymizedPromptCharField


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

    prompt = AnonymizedPromptCharField(
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

    @staticmethod
    def validate_extracted_prompt(prompt, user):
        if fmtr.is_multi_task_prompt(prompt):
            # Multi-task is commercial-only
            if user.has_seat is False:
                raise serializers.ValidationError(
                    {"prompt": "requested prompt format is not supported"}
                )
            task_count = fmtr.get_task_count_from_prompt(prompt)
            if task_count > 10:
                raise serializers.ValidationError({"prompt": "maximum task request size exceeded"})
        else:
            # Confirm the prompt contains some flavor of '- name:'
            match = re.search(r"^[\s]*-[\s]+name[\s]*:", prompt)
            if not match:
                raise serializers.ValidationError(
                    {"prompt": "prompt does not contain the name parameter"}
                )

    def validate(self, data):
        data = super().validate(data)

        data['prompt'], data['context'] = fmtr.extract_prompt_and_context(data['prompt'])
        CompletionRequestSerializer.validate_extracted_prompt(
            data['prompt'], self.context.get('request').user
        )

        # If suggestion ID was not included in the request, set a random UUID to it.
        if data.get('suggestionId') is None:
            data['suggestionId'] = uuid.uuid4()
        return data


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
        fields = ['predictions', 'suggestionId', 'modelName']

    modelName = serializers.CharField(required=False)
    suggestionId = serializers.UUIDField(required=False)
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


class SuggestionQualityFeedback(serializers.Serializer):
    class Meta:
        fields = ['prompt', 'providedSuggestion', 'expectedSuggestion', 'additionalComment']

    prompt = AnonymizedCharField(
        trim_whitespace=False,
        required=True,
        label='File Content used as context',
        help_text='File Content till end of task name description before cursor position.',
    )
    providedSuggestion = AnonymizedCharField(
        trim_whitespace=False,
        required=True,
        label='Provided Model suggestion',
        help_text='Inline suggestion from model as shared by user for given prompt.',
    )
    expectedSuggestion = AnonymizedCharField(
        trim_whitespace=False,
        required=True,
        label='Expected Model suggestion',
        help_text='Suggestion expected by the user.',
    )
    additionalComment = AnonymizedCharField(
        trim_whitespace=False,
        required=False,
        label='Additional Comment',
        help_text='Additional comment describing why the \
                   change was required in Lightspeed suggestion.',
    )


class SentimentFeedback(serializers.Serializer):
    class Meta:
        fields = ['value', 'feedback']

    value = serializers.IntegerField(required=True, min_value=1, max_value=5)

    feedback = AnonymizedCharField(
        trim_whitespace=False,
        required=True,
        label='Free form text feedback',
        help_text='Free form text feedback describing the reason for sentiment value.',
    )


class IssueFeedback(serializers.Serializer):
    ISSUE_TYPE = (('bug-report', 'Bug Report'), ('feature-request', 'Feature Request'))

    class Meta:
        fields = ['type', 'title', 'description']

    type = serializers.ChoiceField(choices=ISSUE_TYPE, required=True)
    title = AnonymizedCharField(
        trim_whitespace=False,
        required=True,
        label='Issue title',
        help_text='The title of the issue.',
    )
    description = AnonymizedCharField(
        trim_whitespace=False,
        required=True,
        label='Issue description',
        help_text='The description of the issue.',
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
        fields = [
            'inlineSuggestion',
            'ansibleContent',
            'suggestionQualityFeedback',
            'sentimentFeedback',
            'issueFeedback',
        ]

    inlineSuggestion = InlineSuggestionFeedback(required=False)
    ansibleContent = AnsibleContentFeedback(required=False)
    suggestionQualityFeedback = SuggestionQualityFeedback(required=False)
    sentimentFeedback = SentimentFeedback(required=False)
    issueFeedback = IssueFeedback(required=False)


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
    UNKNOWN = (-1, "Unknown Source")
    GALAXY_C = (
        0,
        "Ansible Galaxy collections",
    )
    GALAXY_ME = (
        7,
        "Ansible Galaxy documentation",
    )
    GALAXY_R = (
        14,
        "Ansible Galaxy roles",
    )


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


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Valid example',
            summary='Request Sample',
            description='A valid WCA Key request.',
            value={
                'key': '1234567890',
            },
            request_only=True,
            response_only=False,
        ),
    ]
)
class WcaKeyRequestSerializer(serializers.Serializer):
    class Meta:
        fields = ['key']

    key = serializers.CharField(
        trim_whitespace=False,
        required=True,
        label='Key',
        help_text='WCA API Key.',
    )


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Valid example',
            summary='Request Sample',
            description='A valid WCA Model Id request.',
            value={
                'model_id': '1234567890',
            },
            request_only=True,
            response_only=False,
        ),
    ]
)
class WcaModelIdRequestSerializer(serializers.Serializer):
    class Meta:
        fields = ['model_id']

    model_id = serializers.CharField(
        trim_whitespace=False,
        required=True,
        label='Model Id',
        help_text='WCA Model Id.',
    )
