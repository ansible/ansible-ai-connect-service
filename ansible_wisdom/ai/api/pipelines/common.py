import json
from abc import abstractmethod
from typing import Generic, TypeVar

from ai.api.model_client.exceptions import ModelTimeoutError, WcaException
from django.conf import settings
from prometheus_client import Counter
from rest_framework.exceptions import APIException

completions_return_code = Counter(
    'model_prediction_return_code', 'The return code of model prediction requests', ['code']
)
process_error_count = Counter(
    'process_error', "Error counts at pre-process/prediction/post-process stages", ['stage']
)


class PipelineElement:
    @abstractmethod
    def process(self, context) -> None:
        pass


T = TypeVar('T')
C = TypeVar('C')


class Pipeline(Generic[T, C]):
    def __init__(self, pipeline: list[PipelineElement], context: C):
        self.pipeline = pipeline
        self.context = context

    @abstractmethod
    def execute(self) -> T:
        pass


class BaseWisdomAPIException(APIException):
    def __init__(self, *args, cause=None, **kwargs):
        completions_return_code.labels(code=self.status_code).inc()
        super().__init__(*args, **kwargs)
        if settings.SEGMENT_WRITE_KEY and cause and isinstance(self.detail, dict):
            model_id = self.get_model_id_from_exception(cause)
            if model_id:
                self.detail["model"] = model_id

    @staticmethod
    def get_model_id_from_exception(cause):
        """Attempt to get model_id in the request data embedded in a cause."""
        model_id = None
        if isinstance(cause, (WcaException, ModelTimeoutError)):
            model_id = cause.model_id
        elif isinstance(cause, dict) and "model_id" in cause:
            model_id = cause.get("model_id")
        else:
            backend_request_body = getattr(getattr(cause, "request", None), "body", None)
            if backend_request_body:
                try:
                    o = json.loads(backend_request_body)
                    model_id = o.get("model_id", model_id)
                except Exception:
                    pass
        return model_id


class PostprocessException(BaseWisdomAPIException):
    status_code = 204
    error_type = 'postprocess_error'
    default_detail = {"message": "A postprocess error occurred."}


class ModelTimeoutException(BaseWisdomAPIException):
    status_code = 204
    error_type = 'model_timeout'
    default_detail = {"message": "An timeout occurred attempting to complete the request."}


class WcaBadRequestException(BaseWisdomAPIException):
    status_code = 400
    default_detail = {"message": "Bad request for WCA"}


class WcaInvalidModelIdException(BaseWisdomAPIException):
    status_code = 403
    default_detail = {"message": "WCA Model ID is invalid. Please contact your administrator."}


class WcaKeyNotFoundException(BaseWisdomAPIException):
    status_code = 403
    default_detail = {
        "message": "A WCA Api Key was expected but not found. Please contact your administrator."
    }


class WcaModelIdNotFoundException(BaseWisdomAPIException):
    status_code = 403
    default_detail = {
        "message": "A WCA Model ID was expected but not found. Please contact your administrator."
    }


class WcaSuggestionIdCorrelationFailureException(BaseWisdomAPIException):
    status_code = 500
    default_detail = {"message": "WCA Request/Response Suggestion ID correlation failed."}


class WcaEmptyResponseException(BaseWisdomAPIException):
    status_code = 204
    default_detail = {"message": "WCA returned an empty response."}


class ServiceUnavailable(BaseWisdomAPIException):
    status_code = 503
    default_detail = {"message": "An error occurred attempting to complete the request"}


class InternalServerError(BaseWisdomAPIException):
    status_code = 500
    default_detail = {"message": "An error occurred attempting to complete the request"}
