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

from ansible_ai_connect.ai.api.telemetry.schema2 import (
    AnalyticsTelemetryEvents,
    OneClickTrialPlan,
    OneClickTrialStarted,
)
from ansible_ai_connect.ai.api.utils.segment_analytics_telemetry import (
    send_segment_analytics_event,
)

logger = logging.getLogger(__name__)


def oneclick_trial_event_send(user):
    send_segment_analytics_event(
        AnalyticsTelemetryEvents.ONECLICK_TRIAL_STARTED,
        lambda: _oneclick_trial_event_build(user),
        user,
    )


def _oneclick_trial_event_build(user):
    if not user.organization:
        logger.error("Only users within an org are allowed to send trial events.")
        raise ValueError("No user organization specified. Cannot send OneClickTrialStarted.")
    return OneClickTrialStarted(
        plans=[
            OneClickTrialPlan(
                created_at=plan.created_at,
                expired_at=plan.expired_at,
                is_active=plan.is_active,
                name=plan.plan.name,
                id=plan.plan.id,
            )
            for plan in user.userplan_set.all()
        ],
        rh_user_org_id=user.organization.id,
    )
