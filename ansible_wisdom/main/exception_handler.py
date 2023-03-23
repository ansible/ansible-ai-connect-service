from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def exception_handler_with_error_type(exc, context):
    # Call the default exception handler first
    response = exception_handler(exc, context)

    if isinstance(response, Response):
        if exc.status_code == 204:
            response.data = None

        # Add error type if specified
        if hasattr(exc, 'error_type'):
            response.error_type = exc.error_type

    return response
