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

import functools
import json
import logging
from typing import Callable

from django.conf import settings
from rest_framework.exceptions import ValidationError

from ansible_ai_connect.ai.api.exceptions import (
    ModelTimeoutException,
    ServiceUnavailable,
    WcaBadRequestException,
    WcaCloudflareRejectionException,
    WcaEmptyResponseException,
    WcaInvalidModelIdException,
    WcaKeyNotFoundException,
    WcaModelIdNotFoundException,
    WcaNoDefaultModelIdException,
    WcaSuggestionIdCorrelationFailureException,
    WcaUserTrialExpiredException,
)
from ansible_ai_connect.ai.api.model_client.exceptions import (
    ModelTimeoutError,
    WcaBadRequest,
    WcaCloudflareRejection,
    WcaEmptyResponse,
    WcaInvalidModelId,
    WcaKeyNotFound,
    WcaModelIdNotFound,
    WcaNoDefaultModelId,
    WcaSuggestionIdCorrelationFailure,
    WcaUserTrialExpired,
)

logger = logging.getLogger(__name__)


def call(api_type: str, identifier_provider: Callable[[], str]):

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                identifier = identifier_provider()
                value = func(*args, **kwargs)
                return value
            except ModelTimeoutError as e:
                logger.warning(
                    f"model timed out after {settings.ANSIBLE_AI_MODEL_MESH_API_TIMEOUT} "
                    f"seconds (per task) for {api_type}: {identifier}"
                )
                raise ModelTimeoutException(cause=e)

            except WcaBadRequest as e:
                logger.error(
                    f"bad request from WCA for completion for {api_type}: {identifier}:"
                    f" {json.dumps(e.json_response)}"
                )
                raise WcaBadRequestException(cause=e)

            except WcaInvalidModelId as e:
                logger.info(f"WCA Model ID is invalid for {api_type}: {identifier}")
                raise WcaInvalidModelIdException(cause=e)

            except WcaKeyNotFound as e:
                logger.info(
                    f"A WCA Api Key was expected but not found for {api_type}: {identifier}"
                )
                raise WcaKeyNotFoundException(cause=e)

            except WcaNoDefaultModelId as e:
                logger.info(f"No default WCA Model ID was found for {api_type}: {identifier}")
                raise WcaNoDefaultModelIdException(cause=e)

            except WcaModelIdNotFound as e:
                logger.info(
                    f"A WCA Model ID was expected but not found for {api_type}: {identifier}"
                )
                raise WcaModelIdNotFoundException(cause=e)

            except WcaSuggestionIdCorrelationFailure as e:
                logger.info(
                    f"WCA Request/Response SuggestionId correlation failed for "
                    f"{api_type}: {identifier} and x_request_id: {e.x_request_id}"
                )
                raise WcaSuggestionIdCorrelationFailureException(cause=e)

            except WcaEmptyResponse as e:
                logger.info(f"WCA returned an empty response for suggestion {identifier}")
                raise WcaEmptyResponseException(cause=e)

            except WcaCloudflareRejection as e:
                logger.exception(f"Cloudflare rejected the request for {api_type}: {identifier}")
                raise WcaCloudflareRejectionException(cause=e)

            except WcaUserTrialExpired as e:
                logger.exception(f"User trial expired, when requesting {api_type}: {identifier}")
                raise WcaUserTrialExpiredException(cause=e)

            except ValidationError as e:
                logger.exception(
                    f"An exception {e.__class__} occurred "
                    f"during validation of {api_type}: {identifier}"
                )
                raise

            except Exception as e:
                logger.exception(f"error requesting completion for {api_type}: {identifier}")
                raise ServiceUnavailable(cause=e)

        return wrapper

    return decorator
