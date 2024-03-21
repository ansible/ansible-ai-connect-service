import json
import logging
import time
import uuid

from ansible_anonymizer import anonymizer
from django.conf import settings
from django.http import QueryDict
from django.urls import reverse
from rest_framework.exceptions import ErrorDetail
from segment import analytics
from social_django.middleware import SocialAuthExceptionMiddleware

from ansible_wisdom.ai.api.utils import segment_analytics_telemetry
from ansible_wisdom.ai.api.utils.analytics_telemetry_model import (
    AnalyticsRecommendationGenerated,
    AnalyticsRecommendationTask,
    AnalyticsTelemetryEvents,
)
from ansible_wisdom.ai.api.utils.segment import send_segment_event
from ansible_wisdom.ai.api.utils.segment_analytics_telemetry import (
    send_segment_analytics_event,
)
from ansible_wisdom.healthcheck.version_info import VersionInfo

logger = logging.getLogger(__name__)
version_info = VersionInfo()


def on_segment_error(error, _):
    logger.error(f'An error occurred in sending data to Segment: {error}')


def on_segment_analytics_error(error, _):
    logger.error(f'An error occurred in sending analytics data to Segment: {error}')


def anonymize_request_data(data):
    if isinstance(data, QueryDict):
        # See: https://github.com/ansible/ansible-wisdom-service/pull/201#issuecomment-1483015431  # noqa: E501
        new_data = data.copy()
        new_data.update(anonymizer.anonymize_struct(data.dict()))
    else:
        new_data = anonymizer.anonymize_struct(data)
    return new_data


class SegmentMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()

        if settings.SEGMENT_ANALYTICS_WRITE_KEY:
            if not segment_analytics_telemetry.write_key:
                segment_analytics_telemetry.write_key = settings.SEGMENT_ANALYTICS_WRITE_KEY
                segment_analytics_telemetry.debug = settings.DEBUG
                segment_analytics_telemetry.gzip = True  # Enable gzip compression
                # segment_analytics_telemetry.send = False # for code development only
                segment_analytics_telemetry.on_error = on_segment_analytics_error

        if settings.SEGMENT_WRITE_KEY:
            if not analytics.write_key:
                analytics.write_key = settings.SEGMENT_WRITE_KEY
                analytics.debug = settings.DEBUG
                analytics.gzip = True  # Enable gzip compression
                # analytics.send = False # for code development only
                analytics.on_error = on_segment_error

            if request.path == reverse('completions') and request.method == 'POST':
                if request.content_type == 'application/json':
                    try:
                        request_data = (
                            json.loads(request.body.decode("utf-8")) if request.body else {}
                        )
                        request_data = anonymize_request_data(request_data)
                    except Exception:  # when an invalid json or an invalid encoding is detected
                        request_data = {}
                else:
                    request_data = anonymize_request_data(request.POST)

        response = self.get_response(request)

        if settings.SEGMENT_WRITE_KEY:
            if request.path == reverse('completions') and request.method == 'POST':
                request_suggestion_id = getattr(
                    request, '_suggestion_id', request_data.get('suggestionId')
                )
                if not request_suggestion_id:
                    request_suggestion_id = str(uuid.uuid4())
                context = request_data.get('context')
                prompt = request_data.get('prompt')
                model_name = request_data.get('model', '')
                metadata = request_data.get('metadata', {})
                promptType = getattr(request, '_prompt_type', None)

                predictions = None
                message = None
                response_data = getattr(response, 'data', {})

                if isinstance(response_data, dict):
                    predictions = response_data.get('predictions')
                    message = response_data.get('message')
                    if isinstance(message, ErrorDetail):
                        message = str(message)
                    model_name = response_data.get('model', model_name)
                    # Clean up response.data for 204; preserving error information
                    if response.status_code == 204:
                        response.data = {}
                        if response_data.get('code'):
                            response.data.update({'code': response_data.get('code')})
                        if response_data.get('message'):
                            response.data.update({'message': response_data.get('message')})
                    # For other error cases, remove 'model' in response data
                    elif response.status_code >= 400:
                        response_data.pop('model', None)
                elif response.status_code >= 400 and getattr(response, 'content', None):
                    message = str(response.content)

                duration = round((time.time() - start_time) * 1000, 2)
                tasks = getattr(response, 'tasks', [])
                event = {
                    "duration": duration,
                    "request": {"context": context, "prompt": prompt},
                    "response": {
                        "exception": getattr(response, 'exception', None),
                        # See main.exception_handler.exception_handler_with_error_type
                        # That extracts 'default_code' from Exceptions and stores it
                        # in the Response.
                        "error_type": getattr(response, 'error_type', None),
                        "message": message,
                        "predictions": predictions,
                        "status_code": response.status_code,
                        "status_text": getattr(response, 'status_text', None),
                    },
                    "suggestionId": request_suggestion_id,
                    "metadata": metadata,
                    "modelName": model_name,
                    "imageTags": version_info.image_tags,
                    "tasks": tasks,
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
                                    collection=task.get('collection', ''),
                                    module=task.get('module', ''),
                                )
                                for task in tasks
                            ],
                            rh_user_org_id=getattr(request.user, 'org_id', None),
                            suggestion_id=request_suggestion_id,
                            model_name=model_name,
                        ),
                        request.user,
                        getattr(request, '_ansible_extension_version', None),
                    )

        return response


class WisdomSocialAuthExceptionMiddleware(SocialAuthExceptionMiddleware):
    def raise_exception(self, request, exception):
        strategy = getattr(request, 'social_strategy', None)
        if strategy is not None:
            return strategy.setting('RAISE_EXCEPTIONS')  # or settings.DEBUG
