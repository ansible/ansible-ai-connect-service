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

from segment import analytics
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from rest_framework.exceptions import ErrorDetail
from ansible_ai_connect.ai.api.utils.analytics_telemetry_model import (
    AnalyticsRecommendationGenerated,
    AnalyticsRecommendationTask,
    AnalyticsTelemetryEvents,
)
from ansible_ai_connect.ai.api.utils.segment import base_send_segment_event

from ansible_ai_connect.ai.api.utils import segment_analytics_telemetry

from .seated_users_allow_list import ALLOW_LIST
from ansible_ai_connect.ai.api.utils.segment import redact_seated_users_data

from ansible_ai_connect.healthcheck.version_info import VersionInfo
from ansible_ai_connect.main.utils import anonymize_request_data

logger = logging.getLogger(__name__)
version_info = VersionInfo()

def on_segment_error(error, _):
    logger.error(f'An error occurred in sending data to Segment: {error}')


def on_segment_analytics_error(error, _):
    logger.error(f'An error occurred in sending analytics data to Segment: {error}')






class EventRecorder:
    fields_to_preserve = []

    @staticmethod
    def from_request(request):
        classMapping = {
            reverse('explanations'): ExplanationEventRecorder,
            reverse('completions'):  CompletionEventRecorder
        }

        base_class = classMapping.get(request.path)
        if not base_class:
            return
        obj = base_class()
        obj.set_request(request)
        obj.set_request_data(request)
        return obj

   
        
    def __init__(self,):
#    def __init__(self, request=None, response=None, request_data=None):
        self.start_time = time.time()
        self.request_data: dict[str, Any] = {}
        self.model_name: str = ""
        self.event_name: str = "not-set"
        self.exception: bool = False
        self.path: str = ""
        self.response: dict[str, str] = {}
        self.timestamp = timezone.now().isoformat()
        self.hostname: str = platform.node()
        self.imageTags: str = version_info.image_tags
        self.data = {}

    def set_request_data(self, request):
        if request.content_type == 'application/json':
           try:
               request_data = (
                   json.loads(request.body.decode("utf-8")) if request.body else {}
               )
               self.request_data = anonymize_request_data(request_data)
           except Exception:  # when an invalid json or an invalid encoding is detected
               pass

    def set_request(self, request):
        self.path = request.path

        self.event_name = EventRecorder.create_event_name_from_path(request.path)
        self.user = request.user
        self.groups = list(self.user.groups.values_list('name', flat=True))
        self.rh_user_has_seat = getattr(self.user, 'rh_user_has_seat', False)
        self.rh_user_org_id = getattr(self.user, 'org_id', None)

    @staticmethod
    def create_event_name_from_path(path):
        try:
            event_name = path.rstrip("/").split("/")[-1]
            if event_name and event_name.endswith("s"):
                event_name = event_name[:-1]
            return event_name
        except Exception:
            return "unknown"

    def set_exception(self, exc):
        error_code = getattr(exc, 'default_code', None)
        self.exception = {
            "error_code": error_code,
            "exception_class": type(exc).__name__,
            "message": str(exc),
        }

    def set_response(self, response):
        if response.status_code >= 400 and getattr(response, 'content', None):
            message = response.content.decode()
        else:
            message = ""
        self.data = response.data

        self.response = {
            # See main.exception_handler.exception_handler_with_error_type
            # That extracts 'default_code' from Exceptions and stores it
            # in the Response.
            "error_type": getattr(response, 'error_type', None),
            "message": message,
            "status_code": response.status_code,
            "status_text": getattr(response, 'status_text', None),
        }

    def event(self):
        e = {
            "duration": round((time.time() - self.start_time) * 1000, 2),
            "event_name": self.event_name,
            "exception": self.exception,
            "hostname": self.hostname,
            "imageTags": self.imageTags,
            "path": self.path,
            "response": self.response,
            "rh_user_has_seat": self.rh_user_has_seat,
            "rh_user_org_id": self.rh_user_org_id,
            "timestamp": self.timestamp,
        }
        e |= {k: v for k, v in self.request_data.items() if k in self.field_to_preserve}
        return e

    # Note: It could be nice to move the send*() methods somewhere else
    def send(self):
        print("sending!")
        e = self.event()


        if self.rh_user_has_seat:
            allow_list = ALLOW_LIST.get(self.event_name)

            if allow_list:
                e = redact_seated_users_data(e, allow_list)
            else:
                # If event should be tracked, please update ALLOW_LIST appropriately
                logger.error(
                    f'It is not allowed to track {self.event_name} events for seated users'
                )

        if settings.SEGMENT_WRITE_KEY:
            if not analytics.write_key:
                analytics.write_key = settings.SEGMENT_WRITE_KEY
                analytics.debug = settings.DEBUG
                analytics.gzip = True  # Enable gzip compression
                # analytics.send = False # for code development only
                analytics.on_error = on_segment_error
                
        base_send_segment_event(e, self.event_name, self.user, analytics)


    def send_analytics(self):
        if settings.SEGMENT_ANALYTICS_WRITE_KEY:
            if not segment_analytics_telemetry.write_key:
                segment_analytics_telemetry.write_key = settings.SEGMENT_ANALYTICS_WRITE_KEY
                segment_analytics_telemetry.debug = settings.DEBUG
                segment_analytics_telemetry.gzip = True  # Enable gzip compression
                # segment_analytics_telemetry.send = False # for code development only
                segment_analytics_telemetry.on_error = on_segment_analytics_error


class ExplanationEventRecorder(EventRecorder):
    fields_to_preserve = {"explanationId": "explanationId"}
    
class GenerationEventRecorder(EventRecorder):
    fields_to_preserve = {"generationId": "generationId"}

class CompletionEventRecorder(EventRecorder):
    fields_to_preserve = {
        "context": "contex",
        "prompt": "prompt",
        "model": "modelName",  # TODO
        "metadata": "metadata",
        "suggestionId": "suggestionId",
        "metadata": "metadata",
        "_promptType": "promptType",
    }

    def send_analytics(self):
        super().send_analytics()
        response_data = self.data.copy()

        if isinstance(response_data, dict):
            predictions = response_data.get('predictions')
            message = response_data.get('message')
            if isinstance(message, ErrorDetail):
                message = str(message)
            model_name = response_data.get('model', self.model_name)
            # For other error cases, remove 'model' in response data
            if self.response["status_code"] >= 400:
                response_data.pop('model', None)
                # Collect analytics telemetry, when tasks exist.
        tasks = getattr(self.data, 'tasks', [])
        if len(tasks) > 0:
            send_segment_analytics_event(
                AnalyticsTelemetryEvents.RECOMMENDATION_GENERATED,
                lambda: AnalyticsRecommendationGenerated(
                    tasks=[
                        AnalyticsRecommendationTask(
                            collection=task.get('collection', ''),
                            module=task.get('module', ''),
                        )
                        for task in tasks
                    ],
                    rh_user_org_id=self.rh_user_org_id,
                    suggestion_id=request_suggestion_id,
                    model_name=self.model_name,
                ),
                request.user,
                getattr(request, '_ansible_extension_version', None),
            )
