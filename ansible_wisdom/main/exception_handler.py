from rest_framework.response import Response
from rest_framework.views import exception_handler


def exception_handler_with_error_type(exc, context):
    # Call the default exception handler first
    response = exception_handler(exc, context)

    if isinstance(response, Response):
        # Add error type if specified.
        # This is used in Segment Events. The events have an 'error_type' property.
        # We therefore have to keep the same property name to support correlation
        # of _new_ Segment events with _old_ Segment events.
        if hasattr(exc, 'default_code'):
            response.error_type = exc.default_code

        # Discard the default 'detail' property
        # We add the 'code', 'message' and 'model' to 'data' root
        if isinstance(response.data, dict):
            if response.data.get('detail'):
                response.data.pop('detail')

        # Extract 'model_id' from Exception
        _model_id = {'model': exc.model_id} if hasattr(exc, 'model_id') else {}

        # Append 'code' and 'message' to the response data to enable the client
        # to be able to properly present the error to the user; based on 'code'.
        _full_details = exc.get_full_details()

        # Build complete response
        _data = response.data if response.data else {}
        response.data = {**_full_details, **_model_id, **_data}

    return response
