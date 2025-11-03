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

from ansible_anonymizer import anonymizer
from django.conf import settings
from django.middleware.csrf import CsrfViewMiddleware
from rest_framework.exceptions import ErrorDetail, PermissionDenied
from segment import analytics
from social_django.middleware import SocialAuthExceptionMiddleware

from ansible_ai_connect.ai.api.telemetry.schema2 import (
    AnalyticsRecommendationGenerated,
    AnalyticsRecommendationTask,
    AnalyticsTelemetryEvents,
)
from ansible_ai_connect.ai.api.utils import segment_analytics_telemetry
from ansible_ai_connect.ai.api.utils.segment import send_segment_event
from ansible_ai_connect.ai.api.utils.segment_analytics_telemetry import (
    send_segment_analytics_event,
)
from ansible_ai_connect.ai.api.utils.version import api_version_reverse
from ansible_ai_connect.healthcheck.version_info import VersionInfo

logger = logging.getLogger(__name__)
version_info = VersionInfo()


def check_csrf(request):
    django_request = getattr(request, "_request", request)

    reason = CsrfViewMiddleware(get_response=lambda r: None).process_view(
        django_request, None, (), {}
    )

    if reason:
        raise PermissionDenied(detail="CSRF validation failed")


def on_segment_error(error, _):
    logger.error(f"An error occurred in sending data to Segment: {error}")


def on_segment_analytics_error(error, _):
    logger.error(f"An error occurred in sending analytics data to Segment: {error}")


class SegmentMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def _api_completions_paths(self):
        return [
            api_version_reverse("completions", api_version=api_version)
            for api_version in settings.REST_FRAMEWORK.get("ALLOWED_VERSIONS", [])
        ]

    def __call__(self, request):
        start_time = time.time()

        if settings.SEGMENT_ANALYTICS_WRITE_KEY:
            if not segment_analytics_telemetry.write_key:
                segment_analytics_telemetry.write_key = settings.SEGMENT_ANALYTICS_WRITE_KEY
                segment_analytics_telemetry.debug = settings.DEBUG
                segment_analytics_telemetry.gzip = True  # Enable gzip compression
                # segment_analytics_telemetry.send = False # for code development only
                segment_analytics_telemetry.on_error = on_segment_analytics_error

        request_data = {}
        if settings.SEGMENT_WRITE_KEY:
            if not analytics.write_key:
                analytics.write_key = settings.SEGMENT_WRITE_KEY
                analytics.debug = settings.DEBUG
                analytics.gzip = True  # Enable gzip compression
                # analytics.send = False # for code development only
                analytics.on_error = on_segment_error

            if request.path in self._api_completions_paths() and request.method == "POST":
                if request.content_type == "application/json":
                    try:
                        request_data = json.loads(request.body) if request.body else {}
                    except json.decoder.JSONDecodeError:
                        logger.error(f"Cannot parse: {request.body=}")
                        request_data = {}
                else:
                    request_data = request.POST

        response = self.get_response(request)

        if settings.SEGMENT_WRITE_KEY:
            if request.path in self._api_completions_paths() and request.method == "POST":
                request_suggestion_id = getattr(
                    request, "_suggestion_id", request_data.get("suggestionId")
                )
                if not request_suggestion_id:
                    request_suggestion_id = str(uuid.uuid4())
                context = request_data.get("context")
                prompt = request_data.get("prompt")
                model_name = request_data.get("model", "")
                metadata = request_data.get("metadata", {})
                promptType = getattr(request, "_prompt_type", None)

                predictions = None
                message = None
                response_data = getattr(response, "data", {})

                if isinstance(response_data, dict):
                    predictions = response_data.get("predictions")
                    message = response_data.get("message")
                    if isinstance(message, ErrorDetail):
                        message = str(message)
                    model_name = response_data.get("model", model_name)
                    # For other error cases, remove 'model' in response data
                    if response.status_code >= 400:
                        response_data.pop("model", None)
                elif response.status_code >= 400 and getattr(response, "content", None):
                    message = str(response.content)

                duration = round((time.time() - start_time) * 1000, 2)
                tasks = getattr(response, "tasks", [])
                event = {
                    "duration": duration,
                    "request": anonymizer.anonymize_struct({"context": context, "prompt": prompt}),
                    "response": anonymizer.anonymize_struct(
                        {
                            "exception": getattr(response, "exception", None),
                            # See main.exception_handler.exception_handler_with_error_type
                            # That extracts 'default_code' from Exceptions and stores it
                            # in the Response.
                            "error_type": getattr(response, "error_type", None),
                            "message": message,
                            "predictions": predictions,
                            "status_code": response.status_code,
                            "status_text": getattr(response, "status_text", None),
                        }
                    ),
                    "suggestionId": request_suggestion_id,
                    "metadata": anonymizer.anonymize_struct(metadata),
                    "modelName": model_name,
                    "imageTags": version_info.image_tags,
                    "tasks": anonymizer.anonymize_struct(tasks),
                    "promptType": promptType,
                    "taskCount": len(tasks),
                }

                send_segment_event(event, "completion", request.user)

                # Collect analytics telemetry, when tasks exist.
                if len(tasks) > 0:
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
                            suggestion_id=request_suggestion_id,
                            model_name=model_name,
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
