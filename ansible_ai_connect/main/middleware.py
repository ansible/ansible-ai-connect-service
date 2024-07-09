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
from threading import BoundedSemaphore

from django.conf import settings
from django.urls import reverse
from social_django.middleware import SocialAuthExceptionMiddleware

from ansible_ai_connect.ai.api.utils import segment_analytics_telemetry
from ansible_ai_connect.ai.api.utils.analytics_telemetry_model import (
    AnalyticsRecommendationGenerated,
    AnalyticsRecommendationTask,
    AnalyticsTelemetryEvents,
)
from ansible_ai_connect.ai.api.utils.segment import send_schema1_event
from ansible_ai_connect.ai.api.utils.segment_analytics_telemetry import (
    send_segment_analytics_event,  # Schema2
)
from ansible_ai_connect.healthcheck.version_info import VersionInfo

logger = logging.getLogger(__name__)
version_info = VersionInfo()


def on_segment_schema2_error(error, _):
    logger.error(f"An error occurred in sending schema2 data to Segment: {error}")


sema = BoundedSemaphore(value=1)
global_schema1_event = None


class SegmentMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Schema2
        if settings.SEGMENT_ANALYTICS_WRITE_KEY:
            if not segment_analytics_telemetry.write_key:
                segment_analytics_telemetry.write_key = settings.SEGMENT_ANALYTICS_WRITE_KEY
                segment_analytics_telemetry.debug = settings.DEBUG
                segment_analytics_telemetry.gzip = True  # Enable gzip compression
                # segment_analytics_telemetry.send = False # for code development only
                segment_analytics_telemetry.on_error = on_segment_schema2_error

        with sema:
            global_schema1_event
            response = self.get_response(request)
            if global_schema1_event:
                global_schema1_event.set_response(response)
                send_schema1_event(global_schema1_event)

        if settings.SEGMENT_ANALYTICS_WRITE_KEY:
            if request.path == reverse("completions") and request.method == "POST":
                tasks = getattr(response, "tasks", [])
                # Collect analytics telemetry, when tasks exist.
                if len(tasks) > 0:
                    # Schema2
                    send_segment_analytics_event(
                        AnalyticsTelemetryEvents.RECOMMENDATION_GENERATED,
                        lambda: AnalyticsRecommendationGenerated(
                            tasks=[
                                AnalyticsRecommendationTask(
                                    collection=task.get("collection", ""),
                                    module=task.get("module", ""),
                                )
                                for task in tasks
                            ],
                            rh_user_org_id=getattr(request.user, "org_id", None),
                            suggestion_id=getattr(response, "suggestionId", ""),
                            model_name=getattr(request, "_model", None),
                        ),
                        request.user,
                        getattr(request, "_ansible_extension_version", None),
                    )

        # Clean up response.data for 204; should be empty to prevent
        # issues on the client side
        if response.status_code == 204:
            response.data = None
            response["Content-Length"] = 0
            # Set content to empty string so that underlying streaming TCP connections
            # do not read incorrect content when processing HTTP responses after 204s
            response.content = ""
        return response


class WisdomSocialAuthExceptionMiddleware(SocialAuthExceptionMiddleware):
    def raise_exception(self, request, exception):
        strategy = getattr(request, "social_strategy", None)
        if strategy is not None:
            return strategy.setting("RAISE_EXCEPTIONS")  # or settings.DEBUG
