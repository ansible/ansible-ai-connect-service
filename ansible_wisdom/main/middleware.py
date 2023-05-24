import json
import logging
import time
import uuid

from ai.api.utils.segment import send_segment_event
from ansible_anonymizer import anonymizer
from django.conf import settings
from django.http import QueryDict
from django.urls import reverse
from healthcheck.version_info import VersionInfo
from segment import analytics
from social_django.middleware import SocialAuthExceptionMiddleware

logger = logging.getLogger(__name__)
version_info = VersionInfo()


def on_segment_error(error, _):
    logger.error(f'An error occurred in sending data to Segment: {error}')


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
                suggestion_id = getattr(request, '_suggestion_id', request_data.get('suggestionId'))
                if not suggestion_id:
                    suggestion_id = str(uuid.uuid4())
                context = request_data.get('context')
                prompt = request_data.get('prompt')
                metadata = request_data.get('metadata', {})

                predictions = None
                message = None
                response_data = getattr(response, 'data', {})
                if isinstance(response_data, dict):
                    predictions = response_data.get('predictions')
                    message = response_data.get('message')
                elif response.status_code >= 400 and getattr(response, 'content', None):
                    message = str(response.content)

                duration = round((time.time() - start_time) * 1000, 2)
                event = {
                    "duration": duration,
                    "request": {"context": context, "prompt": prompt},
                    "response": {
                        "exception": getattr(response, 'exception', None),
                        "error_type": getattr(response, 'error_type', None),
                        "message": message,
                        "predictions": predictions,
                        "status_code": response.status_code,
                        "status_text": getattr(response, 'status_text', None),
                    },
                    "suggestionId": suggestion_id,
                    "metadata": metadata,
                    "modelName": settings.ANSIBLE_AI_MODEL_NAME,
                    "imageTags": version_info.image_tags,
                }

                send_segment_event(event, "completion", request.user)

        return response


class WisdomSocialAuthExceptionMiddleware(SocialAuthExceptionMiddleware):
    def raise_exception(self, request, exception):
        strategy = getattr(request, 'social_strategy', None)
        if strategy is not None:
            return strategy.setting('RAISE_EXCEPTIONS')  # or settings.DEBUG
