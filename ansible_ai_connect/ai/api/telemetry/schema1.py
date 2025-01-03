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
import time
from string import Template

from ansible_anonymizer import anonymizer
from attr import Factory, asdict, field
from attrs import define, validators
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from yaml.error import MarkedYAMLError

from ansible_ai_connect.healthcheck.version_info import VersionInfo
from ansible_ai_connect.users.models import User

logger = logging.getLogger(__name__)
version_info = VersionInfo()


def anonymize_struct(value):
    return anonymizer.anonymize_struct(value, value_template=Template("{{ _${variable_name}_ }}"))


@define
class RequestPayload:
    method: str = field(validator=validators.instance_of(str), converter=str, default="")
    path: str = field(validator=validators.instance_of(str), converter=str, default="")


@define
class ResponsePayload:
    exception: str = field(validator=validators.instance_of(str), converter=str, default="")
    error_type: str = field(validator=validators.instance_of(str), converter=str, default="")
    message: str = field(validator=validators.instance_of(str), converter=str, default="")
    status_code: int = field(validator=validators.instance_of(int), converter=int, default=0)
    status_text: str = field(validator=validators.instance_of(str), converter=str, default="")


@define
class PlanEntry:
    """Describe one plan associate with the user"""

    accept_marketing: bool = False
    created_at: str = field(validator=validators.instance_of(str), converter=str, default="")
    expired_at: str = field(validator=validators.instance_of(str), converter=str, default="")
    is_active: bool = False
    name: str = field(validator=validators.instance_of(str), converter=str, default="")
    plan_id: int = 0

    @classmethod
    def init(cls, userplan):
        return cls(
            accept_marketing=userplan.accept_marketing,
            created_at=userplan.created_at,
            expired_at=userplan.expired_at,
            is_active=userplan.is_active,
            name=userplan.plan.name,
            plan_id=userplan.plan.id,
        )


@define
class Schema1Event:
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
    request: RequestPayload = RequestPayload()
    response: ResponsePayload = ResponsePayload()
    _user: User | None = None
    _created_at: int = time.time()
    plans: list[PlanEntry] = Factory(list)
    timestamp: str | None = None
    duration: float | None = None

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

    def set_user(self, user):
        self._user = user
        if isinstance(user, AnonymousUser):
            return
        self.rh_user_has_seat = user.rh_user_has_seat
        if user.organization:
            self.rh_user_org_id = user.organization.id
        self.groups = list(user.groups.values_list("name", flat=True))
        self.plans = [PlanEntry.init(up) for up in user.userplan_set.all()]

    def set_request(self, request):
        if hasattr(request, "user"):  # e.g WSGIRequest generated when we run update-openapi-schema
            self.set_user(request.user)
        self.request = RequestPayload(path=request.path, method=request.method)

    def set_response(self, response):
        self.response = {
            # See main.exception_handler.exception_handler_with_error_type
            # That extracts 'default_code' from Exceptions and stores it
            # in the Response.
            "error_type": getattr(response, "error_type", None),
            "status_code": response.status_code,
            "status_text": getattr(response, "status_text", None),
        }

    def finalize(self):
        self.duration = round((time.time() - self._created_at) * 1000, 2)
        self.timestamp = timezone.now().isoformat()

    def as_dict(self):
        self.finalize()

        def my_filter(a, v):
            return a.name not in ["_user", "event_name", "_created_at"]

        return asdict(self, filter=my_filter, recurse=True)


@define
class OneClickTrialStartedEvent(Schema1Event):
    event_name: str = "oneClickTrialStarted"


@define
class ExplainPlaybookEvent(Schema1Event):
    event_name: str = "explainPlaybook"
    playbook_length: int = field(validator=validators.instance_of(int), default=0)
    explanationId: str = field(validator=validators.instance_of(str), converter=str, default="")


@define
class ChatBotResponseDocsReferences:
    docs_url: str = field(validator=validators.instance_of(str), converter=str, default="")
    title: str = field(validator=validators.instance_of(str), converter=str, default="")


@define
class ChatBotBaseEvent(Schema1Event):
    chat_prompt: str = field(validator=validators.instance_of(str), converter=str, default="")
    chat_system_prompt: str = field(
        validator=validators.instance_of(str), converter=str, default=""
    )
    chat_response: str = field(validator=validators.instance_of(str), converter=str, default="")
    chat_truncated: bool = field(
        validator=validators.instance_of(bool), converter=bool, default=False
    )
    chat_referenced_documents: list[ChatBotResponseDocsReferences] = field(factory=list)
    conversation_id: str = field(validator=validators.instance_of(str), converter=str, default="")
    provider_id: str = field(
        validator=validators.instance_of(str),
        converter=str,
        default=settings.CHATBOT_DEFAULT_PROVIDER,
    )

    def __attrs_post_init__(self):
        self.chat_prompt = anonymize_struct(self.chat_prompt)
        self.chat_response = anonymize_struct(self.chat_response)


@define
class ChatBotFeedbackEvent(ChatBotBaseEvent):
    event_name: str = "chatFeedbackEvent"
    sentiment: int = field(
        validator=[validators.instance_of(int), validators.in_([0, 1])], converter=int, default=0
    )


@define
class ChatBotOperationalEvent(ChatBotBaseEvent):
    event_name: str = "chatOperationalEvent"
