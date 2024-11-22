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

from django.conf import settings
from prometheus_client import Counter
from rest_framework.exceptions import APIException

from ansible_ai_connect.ai.api.model_pipelines.exceptions import (
    ModelTimeoutError,
    WcaException,
)

completions_return_code = Counter(
    "model_prediction_return_code", "The return code of model prediction requests", ["code"]
)

process_error_count = Counter(
    "wisdom_service_processing_error",
    "Error counts at pre-process/prediction/post-process etc stages",
    ["stage"],
)


class BaseWisdomAPIException(APIException):
    def __init__(self, *args, cause=None, **kwargs):
        completions_return_code.labels(code=self.status_code).inc()
        super().__init__(*args, **kwargs)
        if settings.SEGMENT_WRITE_KEY and cause:
            model_id = self.get_model_id_from_exception(cause)
            if model_id:
                self.model_id = model_id

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


class WisdomEmptyResponse(BaseWisdomAPIException):
    status_code = 204


class WisdomBadRequest(BaseWisdomAPIException):
    status_code = 400


class WisdomAccessDenied(BaseWisdomAPIException):
    status_code = 403


class PreprocessInvalidYamlException(WisdomBadRequest):
    default_code = "error__preprocess_invalid_yaml"
    default_detail = "Request contains invalid yaml."


class PostprocessException(WisdomEmptyResponse):
    # Do not prefix with error__ to allow correlation with older Segment events
    default_code = "postprocess_error"
    default_detail = "A postprocess error occurred."


class ModelTimeoutException(WisdomEmptyResponse):
    # Do not prefix with error__ to allow correlation with older Segment events
    default_code = "model_timeout"
    default_detail = "An timeout occurred attempting to complete the request."


class WcaBadRequestException(WisdomEmptyResponse):
    default_code = "error__wca_bad_request"
    default_detail = "WCA returned a bad request response."


class WcaInvalidModelIdException(WisdomAccessDenied):
    default_code = "error__wca_invalid_model_id"
    default_detail = "WCA Model ID is invalid. Please contact your administrator."


class WcaKeyNotFoundException(WisdomAccessDenied):
    default_code = "error__wca_key_not_found"
    default_detail = "A WCA Api Key was expected but not found. Please contact your administrator."


class WcaModelIdNotFoundException(WisdomAccessDenied):
    default_code = "error__wca_model_id_not_found"
    default_detail = "A WCA Model ID was expected but not found. Please contact your administrator."


class WcaNoDefaultModelIdException(WisdomAccessDenied):
    default_code = "error__no_default_model_id"
    default_detail = "No default WCA Model ID was found."


class WcaRequestIdCorrelationFailureException(BaseWisdomAPIException):
    status_code = 500
    # This is the old code for when this was used solely for Completions correlation.
    # VSCode will handle both codes identically to maintain compatibility with older services.
    # default_code = "error__wca_suggestion_correlation_failed"
    default_code = "error__wca_request_id_correlation_failed"
    default_detail = "WCA Request/Response Request Id correlation failed."


class WcaEmptyResponseException(WisdomEmptyResponse):
    default_code = "error__wca_empty_response"
    default_detail = "WCA returned an empty response."


class WcaCloudflareRejectionException(WisdomBadRequest):
    default_code = "error__wca_cloud_flare_rejection"
    default_detail = "Cloudflare rejected the request. Please contact your administrator."


class WcaHAPFilterRejectionException(WisdomBadRequest):
    default_code = "error__wca_hap_filter_rejection"
    default_detail = "WCA Hate, Abuse, and Profanity filter rejected the request."


class WcaInstanceDeletedException(BaseWisdomAPIException):
    status_code = 418
    default_code = "error__wca_instance_deleted"
    default_detail = (
        "The WCA instance associated with the Model ID has been deleted."
        "Please contact your administrator."
    )


class WcaInferenceFailureException(WisdomBadRequest):
    default_code = "error__wca_inference_failure"
    default_detail = "WCA inference failed. Completions request failed."


class WcaValidationFailureException(WisdomBadRequest):
    default_code = "error__wca_validation_failure"
    default_detail = "WCA failed to validate response from model. Completions request failed."


class WcaUserTrialExpiredException(WisdomAccessDenied):
    default_code = "permission_denied__user_trial_expired"
    default_detail = "User trial expired. Please contact your administrator."


class ServiceUnavailable(BaseWisdomAPIException):
    status_code = 503
    default_code = "service_unavailable"
    default_detail = "An error occurred attempting to complete the request."


class FeatureNotAvailable(BaseWisdomAPIException):
    status_code = 404
    default_code = "feature_not_available"
    default_detail = "The feature is not available."


class InternalServerError(BaseWisdomAPIException):
    status_code = 500
    default_code = "internal_server"
    default_detail = "An error occurred attempting to complete the request."


class FeedbackValidationException(WisdomBadRequest):
    default_code = "error__feedback_validation"

    def __init__(self, detail, *args, **kwargs):
        super().__init__(detail, *args, **kwargs)


class FeedbackInternalServerException(BaseWisdomAPIException):
    status_code = 500
    default_code = "error__feedback_internal_server"
    default_detail = "Failed to send feedback"


class ChatbotNotEnabledException(BaseWisdomAPIException):
    status_code = 503
    default_code = "error__chatbot_not_enabled"
    default_detail = "Chatbot is not enabled"


class ChatbotInvalidRequestException(WisdomBadRequest):
    default_code = "error__chatbot_invalid_request"
    default_detail = "Invalid request"


class ChatbotInvalidResponseException(BaseWisdomAPIException):
    status_code = 500
    default_code = "error__chatbot_invalid_response"
    default_detail = "Invalid response"


class ChatbotUnauthorizedException(BaseWisdomAPIException):
    """
    Since this exception is on the authentication between
    AI Connect server and Chatbot, which is a backend service,
    status_code 503 (Service Unavailable) is returned to
    client instead of 401.
    """

    status_code = 503
    default_code = "error__chatbot_unauthorized"
    default_detail = "Unauthorized"


class ChatbotForbiddenException(WisdomAccessDenied):
    default_code = "error__chatbot_forbidden"
    default_detail = "Forbidden"


class ChatbotPromptTooLongException(BaseWisdomAPIException):
    status_code = 413
    default_code = "error__chatbot_prompt_too_long"
    default_detail = "Prompt too long"


class ChatbotValidationException(BaseWisdomAPIException):
    status_code = 422
    default_code = "error__chatbot_validation_failed"
    default_detail = "Validation failed"


class ChatbotInternalServerException(BaseWisdomAPIException):
    status_code = 500
    default_code = "error__chatbot_internal_server_error"
    default_detail = "Internal server error"
