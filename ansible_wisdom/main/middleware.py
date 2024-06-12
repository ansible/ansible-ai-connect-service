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

import json
import logging
import time
import uuid

from django.conf import settings
from django.http import QueryDict
from django.urls import reverse
from rest_framework.exceptions import ErrorDetail
from segment import analytics
from social_django.middleware import SocialAuthExceptionMiddleware

# from ansible_ai_connect.ai.api.utils import segment_analytics_telemetry
# from ansible_ai_connect.ai.api.utils.analytics_telemetry_model import (
#     AnalyticsRecommendationGenerated,
#     AnalyticsRecommendationTask,
#     AnalyticsTelemetryEvents,
# )
from ansible_ai_connect.ai.api.utils.segment_recorder import EventRecorder

# from ansible_ai_connect.ai.api.utils.segment_analytics_telemetry import (
#     send_segment_analytics_event,
# )

logger = logging.getLogger(__name__)


class SegmentMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        event_recorder = settings.SEGMENT_ANALYTICS_WRITE_KEY and EventRecorder.from_request(
            request
        )
        event_recorder = EventRecorder.from_request(request)

        response = self.get_response(request)

        # Clean up response.data for 204; should be empty to prevent
        # issues on the client side
        if response.status_code == 204:
            response.data = None
            response['Content-Length'] = 0

        if event_recorder:
            print(event_recorder)
            event_recorder.set_response(response)
            event_recorder.send()
            event_recorder.send_analytics()

        return response


class WisdomSocialAuthExceptionMiddleware(SocialAuthExceptionMiddleware):
    def raise_exception(self, request, exception):
        strategy = getattr(request, 'social_strategy', None)
        if strategy is not None:
            return strategy.setting('RAISE_EXCEPTIONS')  # or settings.DEBUG
