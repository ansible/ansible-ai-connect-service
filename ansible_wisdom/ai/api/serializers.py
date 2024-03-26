"""
DRF Serializer classes for input/output validations and OpenAPI document generation.
"""

import uuid

import yaml
from django.conf import settings
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
        fields = ['ansibleExtensionVersion']

    ansibleExtensionVersion = serializers.RegexField(
        r"v?\d+\.\d+\.\d+",
        required=False,
        label="Ansible vscode/vscodium extension version",
        help_text="User's installed Ansible extension version, in format vMAJOR.MINOR.PATCH",
    )


class CompletionMetadata(Metadata):
    class Meta:
        fields = [
            'documentUri',
            'activityId',
            'ansibleFileType',
            'additionalContext',
            'ansibleExtensionVersion',
        ]

    documentUri = AnonymizedCharField(required=False)
    activityId = serializers.UUIDField(
        format='hex_verbose',
        required=False,
        label="Activity ID",
        help_text="A UUID that identifies a user activity session within a given document.",
    )
    ansibleFileType = serializers.CharField(
        required=False,
        label="Ansible File Type",
        help_text="Ansible file type (playbook/tasks_in_role/tasks)",
    )
    additionalContext = serializers.DictField(
        required=False,
        label="Additional Context",
        help_text="Additional context for completion API",
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
        fields = ['prompt', 'suggestionId', 'metadata', 'model', 'ansibleExtensionVersion']

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
        default=uuid.uuid4,
    )
    metadata = CompletionMetadata(required=False)
    model = serializers.CharField(required=False, allow_blank=True)

    @staticmethod
    def validate_extracted_prompt(prompt, user):
        if fmtr.is_multi_task_prompt(prompt):
            # Multi-task is commercial-only
            if user.rh_user_has_seat is False:
                raise serializers.ValidationError(
                    {"prompt": "requested prompt format is not supported"}
                )

            if '&&' in prompt:
                raise serializers.ValidationError(
                    {"prompt": "multiple task requests should be separated by a single '&'"}
                )

            task_count = fmtr.get_task_count_from_prompt(prompt)
            if task_count > int(settings.MULTI_TASK_MAX_REQUESTS):
                raise serializers.ValidationError({"prompt": "maximum task request size exceeded"})
        else:
            # Confirm the prompt contains some flavor of '- name:'
            prompt_list = yaml.load(prompt, Loader=yaml.SafeLoader)
            if (
                not isinstance(prompt_list, list)
                or len(prompt_list) != 1
                or not isinstance(prompt_list[0], dict)
                or len(prompt_list[0]) != 1
                or 'name' not in prompt_list[0]
            ):
                raise serializers.ValidationError(
                    {"prompt": "prompt does not contain the name parameter"}
                )
            if isinstance(prompt_list[0]['name'], list):
                raise serializers.ValidationError({"prompt": "prompt contains a list"})
            if isinstance(prompt_list[0]['name'], dict):
                raise serializers.ValidationError({"prompt": "prompt contains a dictionary"})

    def validate_model(self, value):
        user = self.context.get('request').user
        if settings.ANSIBLE_AI_ENABLE_TECH_PREVIEW and user.rh_user_has_seat is False:
            raise serializers.ValidationError("user is not entitled to customized model")
        return value

    def validate(self, data):
        data = super().validate(data)

        data['prompt'], data['context'] = fmtr.extract_prompt_and_context(data['prompt'])
        CompletionRequestSerializer.validate_extracted_prompt(
            data['prompt'], self.context.get('request').user
        )

        # If suggestion ID was not included in the request, set a random UUID to it.
        if data.get('suggestionId') is None:
            data['suggestionId'] = uuid.uuid4()

        if "model" in data and not data["model"].strip():
            del data["model"]
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
        fields = ['predictions', 'suggestionId', 'model']

    model = serializers.CharField(required=False)
    suggestionId = serializers.UUIDField(required=False)
    predictions = serializers.ListField(child=serializers.CharField(trim_whitespace=False))


class InlineSuggestionFeedback(serializers.Serializer):
    USER_ACTION_CHOICES = (('0', 'ACCEPTED'), ('1', 'REJECTED'), ('2', 'IGNORED'))

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

    prompt = serializers.CharField(
        trim_whitespace=False,
        required=True,
        label='File Content used as context',
        help_text='File Content till end of task name description before cursor position.',
    )
    providedSuggestion = serializers.CharField(
        trim_whitespace=False,
        required=True,
        label='Provided Model suggestion',
        help_text='Inline suggestion from model as shared by user for given prompt.',
    )
    expectedSuggestion = serializers.CharField(
        trim_whitespace=False,
        required=True,
        label='Expected Model suggestion',
        help_text='Suggestion expected by the user.',
    )
    additionalComment = serializers.CharField(
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

    feedback = serializers.CharField(
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
    title = serializers.CharField(
        trim_whitespace=False,
        required=True,
        label='Issue title',
        help_text='The title of the issue.',
    )
    description = serializers.CharField(
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
            'ansibleExtensionVersion',
        ]

    inlineSuggestion = InlineSuggestionFeedback(required=False)
    ansibleContent = AnsibleContentFeedback(required=False)
    suggestionQualityFeedback = SuggestionQualityFeedback(required=False)
    sentimentFeedback = SentimentFeedback(required=False)
    issueFeedback = IssueFeedback(required=False)
    metadata = Metadata(required=False)
    model = serializers.CharField(required=False)

    def validate_inlineSuggestion(self, value):
        user = self.context.get('request').user

        if user.rh_user_has_seat is False:
            return value
        if user.organization and user.organization.telemetry_opt_out is False:
            return value
        else:
            raise serializers.ValidationError("invalid feedback type for user")

    def validate_ansibleContent(self, value):
        user = self.context.get('request').user

        if user.rh_user_has_seat:
            raise serializers.ValidationError("invalid feedback type for user")
        return value


class AttributionRequestSerializer(serializers.Serializer):
    class Meta:
        fields = ['suggestion', 'suggestionId', 'ansibleExtensionVersion']

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
    metadata = Metadata(required=False)


class ExplanationRequestSerializer(serializers.Serializer):
    class Meta:
        fields = ['content', 'explanationId', 'ansibleExtensionVersion']

    content = serializers.CharField(
        required=True,
        label="Playbook content",
        help_text=("The playbook that needs to be explained."),
    )
    explanationId = serializers.UUIDField(
        format='hex_verbose',
        required=False,
        label="Explanation ID",
        help_text=(
            "A UUID that identifies the particular explanation data is being requested for."
        ),
    )
    metadata = Metadata(required=False)


class ExplanationResponseSerializer(serializers.Serializer):
    content = serializers.CharField()
    format = serializers.CharField()
    explanationId = serializers.UUIDField(
        format='hex_verbose',
        required=False,
        label="Explanation ID",
        help_text=(
            "A UUID that identifies the particular explanation data is being requested for."
        ),
    )


class ContentMatchRequestSerializer(serializers.Serializer):
    class Meta:
        fields = ['suggestions', 'suggestionId', 'model', 'ansibleExtensionVersion']

    suggestions = serializers.ListField(child=AnonymizedCharField(trim_whitespace=False))
    suggestionId = serializers.UUIDField(
        format='hex_verbose',
        required=False,
        label="Suggestion ID",
        help_text=(
            "A UUID that identifies the particular suggestion"
            " attribution data is being requested for."
        ),
    )
    model = serializers.CharField(required=False, allow_blank=True)
    metadata = Metadata(required=False)

    def validate(self, data):
        data = super().validate(data)
        if "model" in data and not data["model"].strip():
            del data["model"]
        return data


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
    path = serializers.CharField(allow_blank=True)
    license = serializers.CharField()
    data_source = EnumField(choices=DataSource)
    ansible_type = EnumField(choices=AnsibleType)
    score = serializers.FloatField()


class AttributionResponseSerializer(serializers.Serializer):
    class Meta:
        fields = ['attributions']

    attributions = serializers.ListField(child=AttributionSerializer())


class ContentMatchSerializer(serializers.Serializer):
    repo_name = serializers.CharField()
    repo_url = serializers.URLField(allow_blank=True)
    path = serializers.CharField(allow_blank=True)
    license = serializers.CharField()
    data_source_description = serializers.CharField()
    score = serializers.FloatField()


class ContentMatchListSerializer(serializers.Serializer):
    class Meta:
        fields = ['contentmatch']

    contentmatch = serializers.ListField(child=ContentMatchSerializer())


class ContentMatchResponseSerializer(serializers.Serializer):
    class Meta:
        fields = ['contentmatches']

    contentmatches = serializers.ListField(child=ContentMatchListSerializer())


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


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Valid example',
            summary='Request Telemetry settings',
            description='A valid request to set the Telemetry settings.',
            value={
                'optOut': 'true',
            },
            request_only=True,
            response_only=False,
        ),
    ]
)
class TelemetrySettingsRequestSerializer(serializers.Serializer):
    class Meta:
        fields = ['optOut']

    optOut = serializers.BooleanField(
        required=True,
        label='OptOut',
        help_text='Indicates whether the Red Hat Organization opts out of telemetry collection.',
    )
