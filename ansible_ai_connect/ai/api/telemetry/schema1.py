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

from attr import Factory, asdict, field
from attrs import define, validators
from django.utils import timezone

from ansible_ai_connect.healthcheck.version_info import VersionInfo
from ansible_ai_connect.users.models import User

logger = logging.getLogger(__name__)
version_info = VersionInfo()


@define
class RequestPayload:
    method: str = field(validator=validators.instance_of(str), converter=str, default="")
    path: str = field(validator=validators.instance_of(str), converter=str, default="")


@define
class PlanEntry:
    accept_marketing: bool = False
    created_at: str = field(validator=validators.instance_of(str), converter=str, default="")
    expired_at: str = field(validator=validators.instance_of(str), converter=str, default="")
    is_active: bool = False
    name: str = field(validator=validators.instance_of(str), converter=str, default="")
    plan_id: int = 0


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
    _user: User | None = None

    def set_user(self, user):
        self._user = user
        self.rh_user_has_seat = user.rh_user_has_seat
        self.rh_user_org_id = user.org_id
        self.groups = list(user.groups.values_list("name", flat=True))

    def set_request(self, request):
        self.set_user(request.user)
        self.request = RequestPayload(path=request.path, method=request.method)

    def as_dict(self):
        # NOTE: The allowed fields should be moved in the event class itslef
        def my_filter(a, v):
            return a.name not in ["_user", "event_name"]

        return asdict(self, filter=my_filter, recurse=True)


@define
class OneClickTrialStartedEvent(Schema1Event):
    event_name: str = "oneClickTrialStarted"
    plans: list[PlanEntry] = Factory(list)

    def set_user(self, user):
        super().set_user(user)
        for up in user.userplan_set.all():
            self.plans.append(
                PlanEntry(
                    accept_marketing=up.accept_marketing,
                    created_at=up.created_at,
                    expired_at=up.expired_at,
                    is_active=up.is_active,
                    name=up.plan.name,
                    plan_id=up.plan.id,
                )
            )
