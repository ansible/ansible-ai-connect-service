from rest_framework.response import Response
from rest_framework.views import exception_handler


def exception_handler_with_error_type(exc, context):
    # Call the default exception handler first
    response = exception_handler(exc, context)

    if isinstance(response, Response):
        if exc.status_code == 204:
            # If modelName is found in response.data, keep it for telemetry.
            # response.data will be cleaned up later in the middleware.
            try:
                model = response.data.get("model")
                response.data = {"model": model} if model else None
            except Exception:
                response.data = None

        # Add error type if specified
        if hasattr(exc, 'error_type'):
            response.error_type = exc.error_type

    return response
