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

import json
import logging
import time
from string import Template

from ansible_anonymizer import anonymizer
from django.apps import apps
from django.conf import settings
from django_prometheus.conf import NAMESPACE
from prometheus_client import Histogram

from ansible_wisdom.ai.api.data.data_model import ModelMeshPayload
from ansible_wisdom.ai.api.exceptions import (
    BaseWisdomAPIException,
    ModelTimeoutException,
    ServiceUnavailable,
    WcaBadRequestException,
    WcaCloudflareRejectionException,
    WcaEmptyResponseException,
    WcaInvalidModelIdException,
    WcaKeyNotFoundException,
    WcaModelIdNotFoundException,
    WcaSuggestionIdCorrelationFailureException,
    WcaUserTrialExpiredException,
    process_error_count,
)
from ansible_wisdom.ai.api.model_client.exceptions import (
    ModelTimeoutError,
    WcaBadRequest,
    WcaCloudflareRejection,
    WcaEmptyResponse,
    WcaInvalidModelId,
    WcaKeyNotFound,
    WcaModelIdNotFound,
    WcaSuggestionIdCorrelationFailure,
    WcaUserTrialExpired,
)
from ansible_wisdom.ai.api.pipelines.common import PipelineElement
from ansible_wisdom.ai.api.pipelines.completion_context import CompletionContext
from ansible_wisdom.ai.api.utils.segment import send_segment_event
from ansible_wisdom.ai.feature_flags import FeatureFlags, WisdomFlags

logger = logging.getLogger(__name__)

feature_flags = FeatureFlags()

completions_hist = Histogram(
    'model_prediction_latency_seconds',
    "Histogram of model prediction processing time",
    namespace=NAMESPACE,
)


def get_model_client(wisdom_app, user):
    if settings.DEPLOYMENT_MODE != 'onprem' and user.rh_user_has_seat:
        return wisdom_app.get_wca_client(), None

    # either onprem or non-seated customers (e.g. upstream)
    # we want onprem to follow simply what ANSIBLE_AI_MODEL_MESH_API_TYPE has dictated
    model_mesh_client = wisdom_app.model_mesh_client
    model_name = None
    if settings.LAUNCHDARKLY_SDK_KEY:
        model_tuple = feature_flags.get(WisdomFlags.MODEL_NAME, user, "")
        logger.debug(f"flag model_name has value {model_tuple}")
        model_parts = model_tuple.split(':')
        if len(model_parts) == 4:
            server, port, model_name, _ = model_parts
            logger.info(f"selecting model '{model_name}@{server}:{port}'")
            model_mesh_client.set_inference_url(f"{server}:{port}")
    return model_mesh_client, model_name


class InferenceStage(PipelineElement):
    def process(self, context: CompletionContext) -> None:
        request = context.request
        payload = context.payload
        model_mesh_client, model_name = get_model_client(apps.get_app_config("ai"), request.user)
        # We have a little inconsistency of the "model" term throughout the application:
        # - FeatureFlags use 'model_name'
        # - ModelMeshClient uses 'model_id'
        # - Public completion API uses 'model'
        # - Segment Events use 'modelName'
        model_id = model_name or payload.model
        suggestion_id = payload.suggestionId

        model_mesh_payload = ModelMeshPayload(
            instances=[
                {
                    "prompt": payload.prompt,
                    "context": payload.context,
                    "userId": str(payload.userId) if payload.userId else None,
                    "rh_user_has_seat": request._request.user.rh_user_has_seat,
                    "organization_id": request._request.user.org_id,
                    "suggestionId": str(suggestion_id),
                }
            ]
        )
        data = model_mesh_payload.dict()
        logger.debug(f"input to inference for suggestion id {suggestion_id}:\n{data}")

        predictions = None
        exception = None
        event = None
        event_name = None
        start_time = time.time()
        try:
            predictions = model_mesh_client.infer(
                data, model_id=model_id, suggestion_id=suggestion_id
            )
            model_id = predictions.get("model_id", model_id)
        except ModelTimeoutError as e:
            exception = e
            logger.warning(
                f"model timed out after {settings.ANSIBLE_AI_MODEL_MESH_API_TIMEOUT} "
                f"seconds (per task) for suggestion {suggestion_id}"
            )
            raise ModelTimeoutException(cause=e)

        except WcaBadRequest as e:
            exception = e
            logger.error(
                f"bad request from WCA for completion for suggestion {payload.suggestionId}:"
                f" {json.dumps(exception.json_response)}"
            )
            raise WcaBadRequestException(cause=e)

        except WcaInvalidModelId as e:
            exception = e
            logger.info(f"WCA Model ID is invalid for suggestion {payload.suggestionId}")
            raise WcaInvalidModelIdException(cause=e)

        except WcaKeyNotFound as e:
            exception = e
            logger.info(f"A WCA Api Key was expected but not found for suggestion {suggestion_id}")
            raise WcaKeyNotFoundException(cause=e)

        except WcaModelIdNotFound as e:
            exception = e
            logger.info(f"A WCA Model ID was expected but not found for suggestion {suggestion_id}")
            raise WcaModelIdNotFoundException(cause=e)

        except WcaSuggestionIdCorrelationFailure as e:
            exception = e
            logger.info(
                f"WCA Request/Response SuggestionId correlation failed for "
                f"suggestion_id: '{suggestion_id}' and x_request_id: '{e.x_request_id}'."
            )
            raise WcaSuggestionIdCorrelationFailureException(cause=e)

        except WcaEmptyResponse as e:
            exception = e
            logger.info(f"WCA returned an empty response for suggestion {payload.suggestionId}")
            raise WcaEmptyResponseException(cause=e)

        except WcaCloudflareRejection as e:
            exception = e
            logger.exception(f"Cloudflare rejected the request for {payload.suggestionId}")
            raise WcaCloudflareRejectionException(cause=e)

        except WcaUserTrialExpired as e:
            exception = e
            logger.exception(
                f"User trial expired, when requesting suggestion {payload.suggestionId}"
            )
            event = {
                "type": "prediction",
                "modelName": model_id,
                "suggestionId": str(suggestion_id),
            }
            event_name = 'trialExpired'
            raise WcaUserTrialExpiredException(cause=e)

        except Exception as e:
            exception = e
            logger.exception(f"error requesting completion for suggestion {suggestion_id}")
            raise ServiceUnavailable(cause=e)

        finally:
            duration = round((time.time() - start_time) * 1000, 2)
            completions_hist.observe(duration / 1000)  # millisec back to seconds
            anonymized_predictions = anonymizer.anonymize_struct(
                predictions, value_template=Template("{{ _${variable_name}_ }}")
            )
            # If an exception was thrown during the backend call, try to get the model ID
            # that is contained in the exception.
            if exception:
                process_error_count.labels(stage='prediction').inc()
                model_id_in_exception = BaseWisdomAPIException.get_model_id_from_exception(
                    exception
                )
                if model_id_in_exception:
                    model_id = model_id_in_exception
            if event:
                event['modelName'] = model_id
            else:
                event = {
                    "duration": duration,
                    "exception": exception is not None,
                    "modelName": model_id,
                    "problem": None if exception is None else exception.__class__.__name__,
                    "request": data,
                    "response": anonymized_predictions,
                    "suggestionId": str(suggestion_id),
                }
            event_name = event_name if event_name else "prediction"
            send_segment_event(event, event_name, request.user)

        logger.debug(f"response from inference for suggestion id {suggestion_id}:\n{predictions}")

        context.model_id = model_id
        context.predictions = predictions
        context.anonymized_predictions = anonymized_predictions
