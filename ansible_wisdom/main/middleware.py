import json
import logging
import time

from django.conf import settings
from django.urls import reverse
from segment import analytics

logger = logging.getLogger(__name__)


def on_segment_error(error, _):
    logger.error(f'An error occurred in sending data to Segment: {error}')


class SegmentMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()

        if settings.SEGMENT_WRITE_KEY:
            if not analytics.write_key:
                analytics.write_key = settings.SEGMENT_WRITE_KEY
                analytics.debug = settings.DEBUG
                # analytics.send = False # for code development only
                analytics.on_error = on_segment_error

            if request.path == reverse('completions') and request.method == 'POST':
                if request.content_type == 'application/json':
                    try:
                        request_data = (
                            json.loads(request.body.decode("utf-8")) if request.body else {}
                        )
                    except Exception:  # when an invalid json or an invalid encoding is detected
                        request_data = {}
                else:
                    request_data = request.POST

        response = self.get_response(request)

        if settings.SEGMENT_WRITE_KEY:
            if request.path == reverse('completions') and request.method == 'POST':
                user_id = str(getattr(request.user, 'uuid', 'unknown'))
                suggestion_id = request_data.get('suggestionId')
                context = request_data.get('context')
                prompt = request_data.get('prompt')
                metadata = request_data.get('metadata', {})

                response_data = getattr(response, 'data', {})
                predictions = response_data.get('predictions')

                duration = round((time.time() - start_time) * 1000, 2)
                event = {
                    "duration": duration,
                    "request": {"context": context, "prompt": prompt},
                    "response": {
                        "exception": getattr(response, 'exception', None),
                        "predictions": predictions,
                        "status_code": response.status_code,
                        "status_text": getattr(response, 'status_text', None),
                    },
                    "suggestionId": suggestion_id,
                    "metadata": metadata,
                }

                analytics.track(
                    user_id,
                    "wisdomServiceCompletionEvent",
                    event,
                )

        return response
