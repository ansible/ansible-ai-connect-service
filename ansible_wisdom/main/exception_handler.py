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
