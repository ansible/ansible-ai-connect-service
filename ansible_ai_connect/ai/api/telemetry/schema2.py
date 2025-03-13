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

from enum import Enum

from attr import Factory, field, frozen
from attrs import validators
from django.utils import timezone

# WARNING!
# EVERY TIME WE ADD A NEW EVENT OR CHANGE A KEY IN THIS FILE, WE MUST ADD @akarve AS REVIEWER


class AnalyticsTelemetryEvents(Enum):
    RECOMMENDATION_GENERATED = "Recommendation Generated"
    RECOMMENDATION_ACTION = "Recommendation Action"
    PRODUCT_FEEDBACK = "Product Feedback"
    PLAYBOOK_GENERATION_ACTION = "Playbook Generation Action"
    ROLE_GENERATION_ACTION = "Role Generation Action"
    ONECLICK_TRIAL_STARTED = "OneClickTrial Started"


@frozen
class AnalyticsRecommendationTask:
    collection: str = field(validator=validators.instance_of(str), converter=str, default="")
    module: str = field(validator=validators.instance_of(str), converter=str, default="")


@frozen
class AnalyticsRecommendationGenerated:
    tasks: list[AnalyticsRecommendationTask] = field(factory=list, validator=validators.min_len(1))
    suggestion_id: str = field(validator=validators.instance_of(str), converter=str, default="")
    rh_user_org_id: int = field(validator=validators.instance_of(int), converter=int, default=0)
    model_name: str = field(default="")
    timestamp: str = field(
        default=Factory(lambda self: timezone.now().isoformat(), takes_self=True)
    )


@frozen
class AnalyticsPlaybookGenerationWizard:
    #  OPEN = 0, // Open wizard
    #  CLOSE = 1, // Close wizard
    #  TRANSITION = 2, // Page transition
    #  ACCEPT = 3
    action: int = field(
        validator=[validators.instance_of(int), validators.in_([0, 1, 2, 3])], converter=int
    )
    model_name: str = field(default="")
    wizard_id: str = field(validator=validators.instance_of(str), converter=str, default="")
    rh_user_org_id: int = field(validator=validators.instance_of(int), converter=int, default=0)
    timestamp: str = field(
        default=Factory(lambda self: timezone.now().isoformat(), takes_self=True)
    )


@frozen
class AnalyticsRoleGenerationWizard(AnalyticsPlaybookGenerationWizard):
    pass


@frozen
class AnalyticsRecommendationAction:
    action: int = field(
        validator=[validators.instance_of(int), validators.in_([0, 1, 2])], converter=int
    )
    suggestion_id: str = field(validator=validators.instance_of(str), converter=str, default="")
    rh_user_org_id: int = field(validator=validators.instance_of(int), converter=int, default=0)
    timestamp: str = field(
        default=Factory(lambda self: timezone.now().isoformat(), takes_self=True)
    )


@frozen
class AnalyticsProductFeedback:
    value: int = field(
        validator=[validators.instance_of(int), validators.in_([1, 2, 3, 4, 5])], converter=int
    )
    rh_user_org_id: int = field(validator=validators.instance_of(int), converter=int, default=0)
    model_name: str = field(default="")
    timestamp: str = field(
        default=Factory(lambda self: timezone.now().isoformat(), takes_self=True)
    )


@frozen
class OneClickTrialPlan:
    created_at: str = field(validator=validators.instance_of(str), converter=str)
    expired_at: str = field(validator=validators.instance_of(str), converter=str)
    is_active: bool
    name: str = field(validator=validators.instance_of(str), converter=str)
    id: int = field(validator=validators.instance_of(int))


@frozen
class OneClickTrialStarted:
    plans: list[OneClickTrialPlan]
    rh_user_org_id: int = field(validator=validators.instance_of(int), converter=int)
    timestamp: str = field(
        default=Factory(lambda self: timezone.now().isoformat(), takes_self=True)
    )
