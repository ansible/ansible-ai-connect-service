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

import logging
import time
from string import Template

from ansible_anonymizer import anonymizer
from django.apps import apps
from django_prometheus.conf import NAMESPACE
from prometheus_client import Histogram

from ansible_ai_connect.ai.api.api_wrapper import call
from ansible_ai_connect.ai.api.data.data_model import ModelMeshPayload
from ansible_ai_connect.ai.api.exceptions import (
    BaseWisdomAPIException,
    WcaUserTrialExpiredException,
    process_error_count,
)
from ansible_ai_connect.ai.api.pipelines.common import PipelineElement
from ansible_ai_connect.ai.api.pipelines.completion_context import CompletionContext
from ansible_ai_connect.ai.api.utils.segment import send_segment_event
from ansible_ai_connect.ai.feature_flags import FeatureFlags

logger = logging.getLogger(__name__)

feature_flags = FeatureFlags()

completions_hist = Histogram(
    "model_prediction_latency_seconds",
    "Histogram of model prediction processing time",
    namespace=NAMESPACE,
)


class InferenceStage2(PipelineElement):
    def process(self, context: CompletionContext) -> None:

        payload = context.payload
        suggestion_id = payload.suggestionId

        @call("suggestions", str(suggestion_id))
        def get_predictions() -> None:
            request = context.request
            model_mesh_client = apps.get_app_config("ai").model_mesh_client
            # We have a little inconsistency of the "model" term throughout the application:
            # - FeatureFlags use 'model_name'
            # - ModelMeshClient uses 'model_id'
            # - Public completion API uses 'model'
            # - Segment Events use 'modelName'
            model_id = payload.model

            model_mesh_payload = ModelMeshPayload(
                instances=[
                    {
                        "prompt": payload.prompt,
                        "context": payload.context,
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
                    request, data, model_id=model_id, suggestion_id=suggestion_id
                )
                model_id = predictions.get("model_id", model_id)

            except WcaUserTrialExpiredException as e:
                exception = e
                event = {
                    "type": "prediction",
                    "modelName": model_id,
                    "suggestionId": str(suggestion_id),
                }
                event_name = "trialExpired"
                raise

            except Exception as e:
                exception = e
                raise
            finally:
                duration = round((time.time() - start_time) * 1000, 2)
                completions_hist.observe(duration / 1000)  # millisec back to seconds
                anonymized_predictions = anonymizer.anonymize_struct(
                    predictions, value_template=Template("{{ _${variable_name}_ }}")
                )
                # If an exception was thrown during the backend call, try to get the model ID
                # that is contained in the exception.
                if exception:
                    process_error_count.labels(stage="prediction").inc()
                    model_id_in_exception = BaseWisdomAPIException.get_model_id_from_exception(
                        exception
                    )
                    if model_id_in_exception:
                        model_id = model_id_in_exception
                if event:
                    event["modelName"] = model_id
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

                logger.debug(
                    f"response from inference for suggestion id {suggestion_id}:\n{predictions}"
                )

                context.model_id = model_id
                context.predictions = predictions
                context.anonymized_predictions = anonymized_predictions

        get_predictions()
