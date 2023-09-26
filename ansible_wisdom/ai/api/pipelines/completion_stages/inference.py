import logging
import time
from string import Template

from ai.api.data.data_model import ModelMeshPayload
from ai.api.model_client.exceptions import ModelTimeoutError
from ai.api.model_client.wca_client import (
    WcaBadRequest,
    WcaEmptyResponse,
    WcaInvalidModelId,
    WcaKeyNotFound,
    WcaModelIdNotFound,
)
from ai.api.pipelines.common import (
    BaseWisdomAPIException,
    ModelTimeoutException,
    PipelineElement,
    ServiceUnavailable,
    WcaBadRequestException,
    WcaEmptyResponseException,
    WcaInvalidModelIdException,
    WcaKeyNotFoundException,
    WcaModelIdNotFoundException,
    process_error_count,
)
from ai.api.utils.segment import send_segment_event
from ai.feature_flags import FeatureFlags, WisdomFlags
from ansible_anonymizer import anonymizer
from django.apps import apps
from django.conf import settings
from django_prometheus.conf import NAMESPACE
from prometheus_client import Histogram

logger = logging.getLogger(__name__)

feature_flags = FeatureFlags()

completions_hist = Histogram(
    'model_prediction_latency_seconds',
    "Histogram of model prediction processing time",
    namespace=NAMESPACE,
)


def get_model_client(wisdom_app, user):
    if user.rh_user_has_seat:
        return wisdom_app.wca_client, None

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
    def process(self, context) -> None:
        request = context["request"]
        payload = context["payload"]
        model_mesh_client, model_name = get_model_client(apps.get_app_config("ai"), request.user)
        # We have a little inconsistency of the "model" term throughout the application:
        # - FeatureFlags use 'model_name'
        # - ModelMeshClient uses 'model_id'
        # - Public completion API uses 'model'
        # - Segment Events use 'modelName'
        model_id = model_name or payload.model

        model_mesh_payload = ModelMeshPayload(
            instances=[
                {
                    "prompt": payload.prompt,
                    "context": payload.context,
                    "userId": str(payload.userId) if payload.userId else None,
                    "rh_user_has_seat": request._request.user.rh_user_has_seat,
                    "organization_id": request._request.user.org_id,
                    "suggestionId": str(payload.suggestionId),
                }
            ]
        )
        data = model_mesh_payload.dict()
        logger.debug(f"input to inference for suggestion id {payload.suggestionId}:\n{data}")

        predictions = None
        exception = None
        start_time = time.time()
        try:
            predictions = model_mesh_client.infer(data, model_id=model_id)
            model_id = predictions.get("model_id", model_id)
        except ModelTimeoutError as e:
            exception = e
            logger.warning(
                f"model timed out after {settings.ANSIBLE_AI_MODEL_MESH_API_TIMEOUT} "
                f"seconds (per task) for suggestion {payload.suggestionId}"
            )
            raise ModelTimeoutException(cause=e)

        except WcaBadRequest as e:
            exception = e
            logger.error(e)
            logger.exception(f"bad request for completion for suggestion {payload.suggestionId}")
            raise WcaBadRequestException(cause=e)

        except WcaInvalidModelId as e:
            exception = e
            logger.error(e)
            logger.exception(f"WCA Model ID is invalid for suggestion {payload.suggestionId}")
            raise WcaInvalidModelIdException(cause=e)

        except WcaKeyNotFound as e:
            exception = e
            logger.error(e)
            logger.exception(
                f"A WCA Api Key was expected but "
                f"not found for suggestion {payload.suggestionId}"
            )
            raise WcaKeyNotFoundException(cause=e)

        except WcaModelIdNotFound as e:
            exception = e
            logger.error(e)
            logger.exception(
                f"A WCA Model ID was expected but "
                f"not found for suggestion {payload.suggestionId}"
            )
            raise WcaModelIdNotFoundException(cause=e)

        except WcaEmptyResponse as e:
            exception = e
            logger.error(e)
            logger.exception(
                f"WCA returned an empty response for suggestion {payload.suggestionId}"
            )
            raise WcaEmptyResponseException(cause=e)

        except Exception as e:
            exception = e
            logger.exception(f"error requesting completion for suggestion {payload.suggestionId}")
            raise ServiceUnavailable(cause=e)

        finally:
            process_error_count.labels(stage='prediction').inc()
            duration = round((time.time() - start_time) * 1000, 2)
            completions_hist.observe(duration / 1000)  # millisec back to seconds
            value_template = Template("{{ _${variable_name}_ }}")
            ano_predictions = anonymizer.anonymize_struct(
                predictions, value_template=value_template
            )
            # If an exception was thrown during the backend call, try to get the model ID
            # that is contained in the exception.
            if exception:
                model_id_in_exception = BaseWisdomAPIException.get_model_id_from_exception(
                    exception
                )
                if model_id_in_exception:
                    model_id = model_id_in_exception
            event = {
                "duration": duration,
                "exception": exception is not None,
                "modelName": model_id,
                "problem": None if exception is None else exception.__class__.__name__,
                "request": data,
                "response": ano_predictions,
                "suggestionId": str(payload.suggestionId),
            }
            send_segment_event(event, "prediction", request.user)

        logger.debug(
            f"response from inference for suggestion id {payload.suggestionId}:\n{predictions}"
        )

        context["model_id"] = model_id
        context["predictions"] = predictions
        context["ano_predictions"] = ano_predictions
