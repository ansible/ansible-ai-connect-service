import rest_framework.exceptions
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

        # We want to return the 'message' and the 'code' to the client to be
        # able to properly present the error to the user.
        if isinstance(exc, rest_framework.exceptions.PermissionDenied):
            response.data = exc.get_full_details()

    return response
