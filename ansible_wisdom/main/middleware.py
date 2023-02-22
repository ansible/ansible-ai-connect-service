import time

from django.conf import settings
from segment import analytics


class SegmentMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()

        response = self.get_response(request)

        if settings.SEGMENT_WRITE_KEY:
            if request.path == '/api/ai/completions/' and request.method == 'POST':
                request_data = getattr(response.renderer_context['request'], 'data', {})

                user_id = request_data.get('userId', 'unknown')
                suggestion_id = request_data.get('suggestionId')
                context = request_data.get('context')
                prompt = request_data.get('prompt')

                predictions = response.data.get('predictions', [])

                duration = round((time.time() - start_time) * 1000, 2)
                event = {
                    "duration": duration,
                    "request": {"context": context, "prompt": prompt},
                    "response": {
                        "exception": response.exception,
                        "predictions": predictions,
                        "status_code": response.status_code,
                        "status_text": response.status_text,
                    },
                    "suggestionId": suggestion_id,
                }

                analytics.write_key = settings.SEGMENT_WRITE_KEY
                analytics.debug = settings.DEBUG
                # analytics.send = False # for code development only

                analytics.track(
                    user_id,
                    "wisdomServiceCompletionEvent",
                    event,
                )

        return response
