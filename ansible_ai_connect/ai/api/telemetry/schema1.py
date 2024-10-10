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

from attr import Factory, asdict, field
from attrs import define, validators
from django.utils import timezone
from yaml.error import MarkedYAMLError

from ansible_ai_connect.healthcheck.version_info import VersionInfo
from ansible_ai_connect.users.models import User

logger = logging.getLogger(__name__)
version_info = VersionInfo()


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
        self.rh_user_has_seat = user.rh_user_has_seat
        self.rh_user_org_id = user.org_id
        self.groups = list(user.groups.values_list("name", flat=True))
        self.plans = [PlanEntry.init(up) for up in user.userplan_set.all()]

    def set_request(self, request):
        self.set_user(request.user)
        self.request = RequestPayload(path=request.path, method=request.method)

    def set_duration(self):
        self.duration = round((time.time() - self._created_at) * 1000, 2)

    def as_dict(self):
        if hasattr(self, "duration") and not self.duration:
            self.set_duration()

        def my_filter(a, v):
            return a.name not in ["_user", "event_name", "_created_at"]

        return asdict(self, filter=my_filter, recurse=True)


@define
class OneClickTrialStartedEvent(Schema1Event):
    event_name: str = "oneClickTrialStarted"


@define
class ExplainPlaybookEvent(Schema1Event):
    event_name: str = "explainPlaybook"
    duration: float | None = None
    playbook_length: int = field(validator=validators.instance_of(int), default=0)
    explanationId: str = field(validator=validators.instance_of(str), converter=str, default="")
