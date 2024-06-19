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

import logging
import platform
import uuid

from attr import Factory, asdict, field
from attrs import define, validators
from django.apps import apps
from django.utils import timezone
from rest_framework.exceptions import ErrorDetail
from yaml.error import MarkedYAMLError

import ansible_ai_connect.ai.api.telemetry.schema1 as schema1
from ansible_ai_connect.ai.api.aws.exceptions import WcaSecretManagerError
from ansible_ai_connect.ai.api.model_client.exceptions import (
    WcaModelIdNotFound,
    WcaNoDefaultModelId,
)
from ansible_ai_connect.ai.api.serializers import (
    CompletionMetadata,
    ContentMatchRequestSerializer,
    SuggestionQualityFeedback,
)
from ansible_ai_connect.healthcheck.version_info import VersionInfo
from ansible_ai_connect.users.models import User

logger = logging.getLogger(__name__)
version_info = VersionInfo()


@define
class ResponsePayload:
    exception: str = field(validator=validators.instance_of(str), converter=str, default="")
    error_type: str = field(validator=validators.instance_of(str), converter=str, default="")
    message: str = field(validator=validators.instance_of(str), converter=str, default="")
    status_code: int = field(validator=validators.instance_of(int), converter=int, default=0)
    status_text: str = field(validator=validators.instance_of(str), converter=str, default="")


@define
class Schema1Event:
    event_name: str = "noName"
    imageTags: str = field(
        validator=validators.instance_of(str), converter=str, default=version_info.image_tags
    )
    hostname: str = field(
        validator=validators.instance_of(str), converter=str, default=platform.node()
    )
    groups: list[str] = Factory(list)

    rh_user_has_seat: bool = False
    rh_user_org_id: int | None = None
    timestamp = timezone.now().isoformat()
    modelName: str = field(validator=validators.instance_of(str), converter=str, default="")
    problem: str = field(validator=validators.instance_of(str), converter=str, default="")
    exception: bool = False
    response: ResponsePayload = ResponsePayload()
    user: User | None = None

    def set_user(self, user):
        self.user = user
        self.rh_user_has_seat = user.rh_user_has_seat
        self.rh_user_org_id = user.org_id
        self.groups = list(user.groups.values_list("name", flat=True))

    def set_exception(self, exception):
        if not exception:
            return
        self.exception = True
        self.response.exception = str(exception)
        self.problem = (
            exception.problem
            if isinstance(exception, MarkedYAMLError)
            else str(exception) if str(exception) else exception.__class__.__name__
        )

    def set_request(self, request):
        pass

    def set_response(self, response):
        def get_message(response):
            if response.status_code < 400:
                return ""
            full_content = str(getattr(response, "content", ""))
            if len(full_content) > 200:
                return full_content[:200] + "…"
            else:
                return full_content

        self.response.status_code = response.status_code
        if response.status_code >= 400:
            self.response.error_type = getattr(response, "error_type", None)
            self.response.message = get_message(response)
            self.response.status_text = (getattr(response, "status_text", None),)

    def set_validated_data(self, validated_data):
        for field_name, value in validated_data.items():
            if hasattr(self, field_name):
                setattr(self, field_name, value)

        # TODO: improve the way we define the model in the payload.
        try:
            model_mesh_client = apps.get_app_config("ai").model_mesh_client
            self.modelName = model_mesh_client.get_model_id(
                self.rh_user_org_id, str(validated_data.get("model", ""))
            )
            print(f"self.modelName={self.rh_user_org_id}")
        except (WcaNoDefaultModelId, WcaModelIdNotFound, WcaSecretManagerError):
            logger.debug(
                f"Failed to retrieve Model Name for Feedback.\n "
                f"Org ID: {self.rh_user_org_id}, "
                f"User has seat: {self.rh_user_has_seat}, "
                f"has subscription: {self.user.rh_org_has_subscription}.\n"
            )

    @classmethod
    def init(cls, user, validated_data):
        print("init()")
        schema1_event = cls()
        schema1_event.set_user(user)
        schema1_event.set_validated_data(validated_data)
        return schema1_event

    def as_dict(self):
        # NOTE: The allowed fields should be moved in the event class itslef
        def my_filter(a, v):
            return a.name not in ["event_name", "user"]

        return asdict(self, filter=my_filter, recurse=True)


@define
class CompletionRequestPayload:
    context: str = field(validator=validators.instance_of(str), converter=str, default="")
    prompt: str = field(validator=validators.instance_of(str), converter=str, default="")


@define
class CompletionEvent(Schema1Event):
    event_name: str = "completion"
    suggestionId: str = field(
        validator=validators.instance_of(str), converter=str, default=uuid.uuid4()
    )
    duration: int = field(validator=validators.instance_of(int), converter=int, default=0)
    promptType: str = ""
    taskCount: int = 0
    metadata: CompletionMetadata = field(default=Factory(dict))
    request: CompletionRequestPayload = CompletionRequestPayload()

    def set_validated_data(self, validated_data):
        super().set_validated_data(validated_data)
        self.request.context = validated_data.get("context")
        self.request.prompt = validated_data.get("prompt")

    def set_request(self, request):
        super().set_request(request)
        self.promptType = getattr(request, "_prompt_type", None)

    def set_response(self, response):
        super().set_response(response)
        # TODO: the way we store the tasks in the response.tasks attribute can
        # certainly be improved
        tasks = getattr(response, "tasks", [])
        self.taskCount = len(tasks)
        self.modelName = getattr(response, "_model", "")


@define
class PostprocessLint(Schema1Event):
    event_name: str = "postprocessLint"
    duration: int = field(validator=validators.instance_of(int), converter=int, default=0)
    postprocessed: str = ""
    problem: str = ""
    recommendation: str = ""
    suggestionId: str = field(validator=validators.instance_of(str), converter=str, default="")


@define
class Postprocess(Schema1Event):
    event_name: str = "postprocess"
    details: str = ""
    duration: int = field(validator=validators.instance_of(int), converter=int, default=0)
    postprocessed: str = ""
    problem: str = ""
    recommendation: str = ""
    suggestionId: str = field(validator=validators.instance_of(str), converter=str, default="")
    truncated: str = ""


@define
class ExplainPlaybookEvent(Schema1Event):
    event_name: str = "explainPlaybook"
    explanationId: str = field(validator=validators.instance_of(str), converter=str, default="")
    duration: int = field(validator=validators.instance_of(int), converter=int, default=0)
    playbook_length: int = field(validator=validators.instance_of(int), converter=int, default=0)

    def set_validated_data(self, validated_data):
        super().set_validated_data(validated_data)
        self.playbook_length = len(validated_data["content"])


@define
class CodegenPlaybookEvent(Schema1Event):
    event_name: str = "codegenPlaybook"
    generationId: str = field(validator=validators.instance_of(str), converter=str, default="")
    wizardId: str = field(validator=validators.instance_of(str), converter=str, default="")
    duration: int = field(validator=validators.instance_of(int), converter=int, default=0)


@define
class ContentMatchEvent(Schema1Event):
    event_name: str = "codematch"
    duration: int = field(validator=validators.instance_of(int), converter=int, default=0)
    request: ContentMatchRequestSerializer | None = None
    metadata: list = field(factory=list)
    problem: str = ""

    def set_validated_data(self, validated_data):
        super().set_validated_data(validated_data)
        self.request = validated_data


# Events associated with the Feedback view
@define
class BaseFeedbackEvent(Schema1Event):
    def set_validated_data(self, validated_data):
        # This is to deal with a corner case that will be address once
        # https://github.com/ansible/vscode-ansible/pull/1408 is merged
        if self.event_name == "inlineSuggestionFeedback" and "inlineSuggestion" in validated_data:
            event_key = "inlineSuggestion"
        else:
            event_key = self.event_name
        suggestion_quality_data: SuggestionQualityFeedback = validated_data[event_key]
        super().set_validated_data(suggestion_quality_data)

    @classmethod
    def init(cls, user, validated_data):
        mapping = {
            "inlineSuggestion": schema1.InlineSuggestionFeedbackEvent,
            "inlineSuggestionFeedback": schema1.InlineSuggestionFeedbackEvent,
            "suggestionQualityFeedback": schema1.SuggestionQualityFeedbackEvent,
            "sentimentFeedback": schema1.InlineSuggestionFeedbackEvent,
            "issueFeedback": schema1.IssueFeedbackEvent,
            "playbookExplanationFeedback": schema1.PlaybookExplanationFeedbackEvent,
            "playbookGenerationAction": schema1.PlaybookGenerationActionEvent,
        }
        # TODO: handles the key that are at the root level of the structure
        for key_name, schema1_class in mapping.items():
            if key_name in validated_data:
                schema1_event = schema1_class()
                schema1_event.set_user(user)
                schema1_event.set_validated_data(validated_data)
                return schema1_event
        print("Failed to init BaseFeedbackEvent")


@define
class InlineSuggestionFeedbackEvent(BaseFeedbackEvent):
    event_name: str = "inlineSuggestionFeedback"
    latency: float = field(validator=validators.instance_of(float), converter=float, default=0.0)
    userActionTime: int = field(validator=validators.instance_of(int), converter=int, default=0)
    action: int = field(validator=validators.instance_of(int), converter=int, default=0)
    suggestionId: str = field(validator=validators.instance_of(str), converter=str, default="")
    activityId: str = field(validator=validators.instance_of(str), converter=str, default="")

    # Remove the method one year after https://github.com/ansible/vscode-ansible/pull/1408 is merged
    # and released
    def set_validated_data(self, validated_data):
        super().set_validated_data(validated_data)


@define
class SuggestionQualityFeedbackEvent(BaseFeedbackEvent):
    event_name: str = "suggestionQualityFeedback"
    prompt: str = field(validator=validators.instance_of(str), converter=str, default="")
    providedSuggestion: str = field(
        validator=validators.instance_of(str), converter=str, default=""
    )
    expectedSuggestion: str = field(
        validator=validators.instance_of(str), converter=str, default=""
    )
    additionalComment: str = field(validator=validators.instance_of(str), converter=str, default="")


@define
class SentimentFeedbackEvent(BaseFeedbackEvent):
    event_name: str = "sentimentFeedback"
    value: int = field(validator=validators.instance_of(int), converter=int, default=0)
    feedback: str = field(validator=validators.instance_of(str), converter=str, default="")


@define
class IssueFeedbackEvent(BaseFeedbackEvent):
    event_name: str = "issueFeedback"
    type: str = field(validator=validators.instance_of(str), converter=str, default="")
    title: str = field(validator=validators.instance_of(str), converter=str, default="")
    description: str = field(validator=validators.instance_of(str), converter=str, default="")


@define
class PlaybookExplanationFeedbackEvent(BaseFeedbackEvent):
    event_name: str = "playbookExplanationFeedback"
    action: int = field(validator=validators.instance_of(int), converter=int, default=0)
    explanation_id: str = field(validator=validators.instance_of(str), converter=str, default="")


@define
class PlaybookGenerationActionEvent(BaseFeedbackEvent):
    event_name: str = "playbookGenerationAction"
    action: int = field(validator=validators.instance_of(int), converter=int, default=0)
    from_page: int = field(validator=validators.instance_of(int), converter=int, default=0)
    to_page: int = field(validator=validators.instance_of(int), converter=int, default=0)
    wizard_id: str = field(validator=validators.instance_of(str), converter=str, default="")
