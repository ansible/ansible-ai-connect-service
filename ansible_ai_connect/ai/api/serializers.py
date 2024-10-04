#  Copyright Red Hat
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

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
from .fields import (
    AnonymizedAdditionalContextField,
    AnonymizedCharField,
    AnonymizedPromptCharField,
)


class Metadata(serializers.Serializer):
    class Meta:
        fields = ["ansibleExtensionVersion"]

    ansibleExtensionVersion = serializers.RegexField(
        r"v?\d+\.\d+\.\d+",
        required=False,
        label="Ansible vscode/vscodium extension version",
        help_text="User's installed Ansible extension version, in format vMAJOR.MINOR.PATCH",
    )


class CompletionMetadata(Metadata):
    class Meta:
        fields = [
            "documentUri",
            "activityId",
            "ansibleFileType",
            "additionalContext",
            "ansibleExtensionVersion",
        ]

    documentUri = AnonymizedCharField(required=False)
    activityId = serializers.UUIDField(
        format="hex_verbose",
        required=False,
        label="Activity ID",
        help_text="A UUID that identifies a user activity session within a given document.",
    )
    ansibleFileType = serializers.CharField(
        required=False,
        label="Ansible File Type",
        help_text="Ansible file type (playbook/tasks_in_role/tasks)",
    )
    additionalContext = AnonymizedAdditionalContextField(
        required=False,
        label="Additional Context",
        help_text="Additional context for completion API",
    )


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Valid example",
            summary="Request Sample",
            description="A valid sample request.",
            value={
                "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n  - name: Install ssh\n",
            },
            request_only=True,
            response_only=False,
        ),
    ]
)
class CompletionRequestSerializer(Metadata):

    prompt = AnonymizedPromptCharField(
        trim_whitespace=False,
        required=True,
        label="Prompt",
        help_text="Editor prompt.",
    )
    suggestionId = serializers.UUIDField(
        format="hex_verbose",
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

            if "&&" in prompt:
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
                or "name" not in prompt_list[0]
            ):
                raise serializers.ValidationError(
                    {"prompt": "prompt does not contain the name parameter"}
                )
            if isinstance(prompt_list[0]["name"], list):
                raise serializers.ValidationError({"prompt": "prompt contains a list"})
            if isinstance(prompt_list[0]["name"], dict):
                raise serializers.ValidationError({"prompt": "prompt contains a dictionary"})

    def validate_model(self, value):
        user = self.context.get("request").user
        if settings.ANSIBLE_AI_ENABLE_TECH_PREVIEW and user.rh_user_has_seat is False:
            raise serializers.ValidationError("user is not entitled to customized model")
        return value

    def validate(self, data):
        data = super().validate(data)

        data["prompt"], data["context"] = fmtr.extract_prompt_and_context(data["prompt"])
        CompletionRequestSerializer.validate_extracted_prompt(
            data["prompt"], self.context.get("request").user
        )

        # If suggestion ID was not included in the request, set a random UUID to it.
        if data.get("suggestionId") is None:
            data["suggestionId"] = uuid.uuid4()

        if "model" in data and not data["model"].strip():
            del data["model"]
        return data


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Valid example",
            summary="Response sample",
            description="A valid sample response.",
            value={
                "predictions": [
                    "    ansible.builtin.package:\n      name: openssh-server\n      state: present"
                ]
            },
            request_only=False,
            response_only=True,
        ),
    ]
)
class CompletionResponseSerializer(serializers.Serializer):
    model = serializers.CharField(required=False)
    suggestionId = serializers.UUIDField(required=False)
    predictions = serializers.ListField(child=serializers.CharField(trim_whitespace=False))


class InlineSuggestionFeedback(serializers.Serializer):
    USER_ACTION_CHOICES = (("0", "ACCEPTED"), ("1", "REJECTED"), ("2", "IGNORED"))

    userActionTime = serializers.FloatField(required=False)
    documentUri = AnonymizedCharField(required=False)
    action = serializers.ChoiceField(choices=USER_ACTION_CHOICES)
    error = AnonymizedCharField(required=False)
    suggestionId = serializers.UUIDField(
        format="hex_verbose",
        required=True,
        label="Suggestion ID",
        help_text="A UUID that identifies a suggestion.",
    )


class SuggestionQualityFeedback(serializers.Serializer):
    prompt = serializers.CharField(
        trim_whitespace=False,
        required=True,
        label="File Content used as context",
        help_text="File Content till end of task name description before cursor position.",
    )
    providedSuggestion = serializers.CharField(
        trim_whitespace=False,
        required=True,
        label="Provided Model suggestion",
        help_text="Inline suggestion from model as shared by user for given prompt.",
    )
    expectedSuggestion = serializers.CharField(
        trim_whitespace=False,
        required=True,
        label="Expected Model suggestion",
        help_text="Suggestion expected by the user.",
    )
    additionalComment = serializers.CharField(
        trim_whitespace=False,
        required=False,
        label="Additional Comment",
        help_text="Additional comment describing why the \
                   change was required in suggestion.",
    )


class SentimentFeedback(serializers.Serializer):
    value = serializers.IntegerField(required=True, min_value=1, max_value=5)

    feedback = serializers.CharField(
        trim_whitespace=False,
        required=True,
        label="Free form text feedback",
        help_text="Free form text feedback describing the reason for sentiment value.",
    )


class IssueFeedback(serializers.Serializer):
    ISSUE_TYPE = (("bug-report", "Bug Report"), ("feature-request", "Feature Request"))

    type = serializers.ChoiceField(choices=ISSUE_TYPE, required=True)
    title = serializers.CharField(
        trim_whitespace=False,
        required=True,
        label="Issue title",
        help_text="The title of the issue.",
    )
    description = serializers.CharField(
        trim_whitespace=False,
        required=True,
        label="Issue description",
        help_text="The description of the issue.",
    )


class PlaybookGenerationFeedback(serializers.Serializer):
    USER_ACTION_CHOICES = (("0", "ACCEPTED"), ("1", "REJECTED"), ("2", "IGNORED"))

    action = serializers.ChoiceField(choices=USER_ACTION_CHOICES, required=True)
    wizardId = serializers.UUIDField(
        format="hex_verbose",
        required=True,
        label="Outline ID",
        help_text="A UUID that identifies the UI session.",
    )


class PlaybookGenerationAction(serializers.Serializer):
    ACTIONS = (("0", "OPEN"), ("1", "CLOSE_CANCEL"), ("2", "TRANSITION"), ("3", "CLOSE_ACCEPT"))

    action = serializers.ChoiceField(choices=ACTIONS, required=True)
    wizardId = serializers.UUIDField(
        format="hex_verbose",
        required=True,
        label="wizard ID",
        help_text="A UUID that identifies the UI session.",
    )
    fromPage = serializers.IntegerField(
        required=False,
        label="page of origin",
        help_text=("A number that indicate the page of origin"),
    )
    toPage = serializers.IntegerField(
        required=False,
        label="destination page",
        help_text=("A number that indicate the destination page"),
    )


class PlaybookExplanationFeedback(serializers.Serializer):
    USER_ACTION_CHOICES = (("0", "ACCEPTED"), ("1", "REJECTED"), ("2", "IGNORED"))

    action = serializers.ChoiceField(choices=USER_ACTION_CHOICES, required=True)
    explanationId = serializers.UUIDField(
        format="hex_verbose",
        required=True,
        label="Explanation ID",
        help_text="A UUID that identifies the playbook explanation.",
    )


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Valid inline suggestion feedback example",
            summary="Feedback Request sample for inline suggestion "
            "to identify if the suggestion is accepted or ignored.",
            description="A valid inline suggestion feedback sample "
            "request to get details about the suggestion like "
            "user decision time, user action and suggestion id.",
            value={
                "inlineSuggestion": {
                    "userActionTime": 5155,
                    "action": "0",
                    "suggestionId": "a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6",
                }
            },
            request_only=True,
            response_only=False,
        ),
    ]
)
class FeedbackRequestSerializer(Metadata):

    inlineSuggestion = InlineSuggestionFeedback(required=False)
    issueFeedback = IssueFeedback(required=False)
    metadata = Metadata(required=False)
    model = serializers.CharField(required=False)
    playbookExplanationFeedback = PlaybookExplanationFeedback(required=False)
    playbookGenerationFeedback = PlaybookGenerationFeedback(required=False)
    playbookGenerationAction = PlaybookGenerationAction(required=False)
    sentimentFeedback = SentimentFeedback(required=False)
    suggestionQualityFeedback = SuggestionQualityFeedback(required=False)

    def validate_inlineSuggestion(self, value):
        user = self.context.get("request").user

        if user.rh_user_has_seat is False:
            return value
        if user.organization and user.organization.has_telemetry_opt_out is False:
            return value
        else:
            raise serializers.ValidationError("invalid feedback type for user")


class ExplanationRequestSerializer(Metadata):

    content = AnonymizedCharField(
        required=True,
        label="Playbook content",
        help_text=("The playbook that needs to be explained."),
    )
    customPrompt = serializers.CharField(
        trim_whitespace=False,
        required=False,
        label="Custom prompt",
        help_text="Custom prompt passed to the LLM when explaining a playbook.",
    )
    explanationId = serializers.UUIDField(
        format="hex_verbose",
        required=False,
        label="Explanation ID",
        help_text=(
            "A UUID that identifies the particular explanation data is being requested for."
        ),
    )
    model = serializers.CharField(required=False, allow_blank=True)
    metadata = Metadata(required=False)

    def validate(self, data):
        data = super().validate(data)

        custom_prompt = data.get("customPrompt")
        if custom_prompt and "{playbook}" not in custom_prompt:
            raise serializers.ValidationError(
                {"customPrompt": "'{playbook}' placeholder expected."}
            )

        return data


class ExplanationResponseSerializer(serializers.Serializer):
    content = serializers.CharField()
    format = serializers.CharField()
    explanationId = serializers.UUIDField(
        format="hex_verbose",
        required=False,
        label="Explanation ID",
        help_text=(
            "A UUID that identifies the particular explanation data is being requested for."
        ),
    )


class GenerationRequestSerializer(serializers.Serializer):
    class Meta:
        fields = [
            "text",
            "generationId",
            "wizardId",
            "createOutline",
            "customPrompt",
            "ansibleExtensionVersion",
            "outline",
        ]

    text = AnonymizedCharField(
        required=True,
        label="Description content",
        help_text=("The description that needs to be converted to a playbook."),
    )
    customPrompt = serializers.CharField(
        trim_whitespace=False,
        required=False,
        label="Custom prompt",
        help_text="Custom prompt passed to the LLM when generating the text of a playbook.",
    )
    generationId = serializers.UUIDField(
        format="hex_verbose",
        required=False,
        label="generation ID",
        help_text=("A UUID that identifies the particular generation data is being requested for."),
    )
    createOutline = serializers.BooleanField(
        required=False,
        default=False,
        label="generate outline",
        help_text=(
            "Indicates whether the answer should also include an outline "
            "of the Ansible Playbook."
        ),
    )
    outline = AnonymizedCharField(
        required=False,
        label="outline",
        help_text="A long step by step outline of the expected Ansible Playbook.",
    )
    wizardId = serializers.UUIDField(
        format="hex_verbose",
        required=False,
        label="wizard ID",
        help_text=("A UUID to track the succession of interaction from the user."),
    )
    model = serializers.CharField(required=False, allow_blank=True)

    metadata = Metadata(required=False)

    def validate(self, data):
        data = super().validate(data)

        outline = data.get("outline")
        custom_prompt = data.get("customPrompt")
        if custom_prompt:
            if "{goal}" not in custom_prompt:
                raise serializers.ValidationError(
                    {"customPrompt": "'{goal}' placeholder expected."}
                )
            if outline and "{outline}" not in custom_prompt:
                raise serializers.ValidationError(
                    {"customPrompt": "'{outline}' placeholder expected when 'outline' provided."}
                )

        return data


class GenerationWarningResponseSerializer(serializers.Serializer):
    id = serializers.CharField()
    message = serializers.CharField()
    details = serializers.CharField(required=False)


class GenerationResponseSerializer(serializers.Serializer):
    playbook = serializers.CharField()
    format = serializers.CharField()
    generationId = serializers.UUIDField(
        format="hex_verbose",
        required=False,
        label="Explanation ID",
        help_text=("A UUID that identifies the particular summary data is being requested for."),
    )
    outline = serializers.CharField()
    warnings = serializers.ListField(child=GenerationWarningResponseSerializer(), required=False)


class ContentMatchRequestSerializer(Metadata):
    suggestions = serializers.ListField(child=AnonymizedCharField(trim_whitespace=False))
    suggestionId = serializers.UUIDField(
        format="hex_verbose",
        required=False,
        label="Suggestion ID",
        help_text=(
            "A UUID that identifies the particular suggestion"
            " content match data is being requested for."
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
    default_error_messages = {"invalid_choice": _('"{input}" is not a valid choice.')}

    def __init__(self, choices, **kwargs):
        self.choices = choices
        self.allow_blank = kwargs.pop("allow_blank", False)

        super().__init__(**kwargs)

    def to_internal_value(self, data):
        try:
            return self.choices(self.choices._member_type_(data))
        except ValueError:
            pass

        try:
            return self.choices["UNKNOWN"]
        except KeyError:
            self.fail("invalid_choice", input=data)

    def to_representation(self, value):
        return value.label


class ContentMatchSerializer(serializers.Serializer):
    repo_name = serializers.CharField()
    repo_url = serializers.URLField(allow_blank=True)
    path = serializers.CharField(allow_blank=True)
    license = serializers.CharField()
    data_source_description = serializers.CharField()
    score = serializers.FloatField()


class ContentMatchListSerializer(serializers.Serializer):
    contentmatch = serializers.ListField(child=ContentMatchSerializer())


class ContentMatchResponseSerializer(serializers.Serializer):
    contentmatches = serializers.ListField(child=ContentMatchListSerializer())


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Valid example",
            summary="Request Sample",
            description="A valid WCA Key request.",
            value={
                "key": "1234567890",
            },
            request_only=True,
            response_only=False,
        ),
    ]
)
class WcaKeyRequestSerializer(serializers.Serializer):
    class Meta:
        fields = ["key"]

    key = serializers.CharField(
        trim_whitespace=False,
        required=True,
        label="Key",
        help_text="WCA API Key.",
    )


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Valid example",
            summary="Request Sample",
            description="A valid WCA Model Id request.",
            value={
                "model_id": "1234567890",
            },
            request_only=True,
            response_only=False,
        ),
    ]
)
class WcaModelIdRequestSerializer(serializers.Serializer):
    model_id = serializers.CharField(
        trim_whitespace=False,
        required=True,
        label="Model Id",
        help_text="WCA Model Id.",
    )


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Valid example",
            summary="Request Telemetry settings",
            description="A valid request to set the Telemetry settings.",
            value={
                "optOut": "true",
            },
            request_only=True,
            response_only=False,
        ),
    ]
)
class TelemetrySettingsRequestSerializer(serializers.Serializer):
    optOut = serializers.BooleanField(
        required=True,
        label="OptOut",
        help_text="Indicates whether the Red Hat Organization opts out of telemetry collection.",
    )
