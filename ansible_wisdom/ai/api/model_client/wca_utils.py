from abc import abstractmethod
from typing import Generic, TypeVar

from .exceptions import (
    WcaBadRequest,
    WcaCloudflareRejection,
    WcaEmptyResponse,
    WcaInvalidModelId,
    WcaTokenFailureApiKeyError,
    WcaUserTrialExpired,
)

T = TypeVar('T')


class Check(Generic[T]):
    @abstractmethod
    def check(self, context: T):
        pass


class Checks(Generic[T]):
    checks: []

    def __init__(self, checks: []):
        self.checks = checks

    def run_checks(self, context: T):
        for check in self.checks:
            check.check(context)


class TokenContext:
    def __init__(self, result):
        self.result = result


class TokenResponseChecks(Checks[TokenContext]):
    class ResponseStatusCode400Missing(Check[TokenContext]):
        def check(self, context: TokenContext):
            if context.result.status_code == 400:
                payload_error = context.result.json().get("errorMessage")
                if payload_error and "property missing or empty" in payload_error.lower():
                    raise WcaTokenFailureApiKeyError()

    class ResponseStatusCode400NotFound(Check[TokenContext]):
        def check(self, context: TokenContext):
            if context.result.status_code == 400:
                payload_error = context.result.json().get("errorMessage")
                if payload_error and "provided api key could not be found" in payload_error.lower():
                    raise WcaTokenFailureApiKeyError()

    def __init__(self):
        super().__init__(
            [
                # The ordering of these checks is important!
                TokenResponseChecks.ResponseStatusCode400Missing(),
                TokenResponseChecks.ResponseStatusCode400NotFound(),
            ]
        )


class InferenceContext:
    def __init__(self, model_id, result, is_multi_task_prompt):
        self.model_id = model_id
        self.result = result
        self.is_multi_task_prompt = is_multi_task_prompt


class InferenceResponseChecks(Checks[InferenceContext]):
    class ResponseStatusCode204(Check[InferenceContext]):
        def check(self, context: InferenceContext):
            if context.result.status_code == 204:
                raise WcaEmptyResponse(model_id=context.model_id)

    class ResponseStatusCode400WCABadRequestModelId(Check[InferenceContext]):
        def check(self, context: InferenceContext):
            if context.result.status_code == 400:
                payload_json = context.result.json()
                if isinstance(payload_json, dict):
                    payload_error = payload_json.get("error")
                    if (
                        payload_error
                        and "bad request" in payload_error.lower()
                        and "('body', 'model_id')" in payload_error.lower()
                    ):
                        raise WcaInvalidModelId(model_id=context.model_id)
                    payload_detail = payload_json.get("detail")
                    if (
                        payload_detail
                        and "failed to parse space id and model id" in payload_detail.lower()
                    ):
                        raise WcaInvalidModelId(model_id=context.model_id)

    class ResponseStatusCode400(Check[InferenceContext]):
        def check(self, context: InferenceContext):
            if context.result.status_code == 400:
                raise WcaBadRequest(model_id=context.model_id, json_response=context.result.json())

    class ResponseStatusCode403(Check[InferenceContext]):
        def check(self, context: InferenceContext):
            if context.result.status_code == 403:
                raise WcaInvalidModelId(model_id=context.model_id)

    class ResponseStatusCode403Cloudflare(Check[InferenceContext]):
        def check(self, context: InferenceContext):
            if context.result.status_code == 403:
                text = context.result.text
                if text and "cloudflare" in text.lower():
                    raise WcaCloudflareRejection(model_id=context.model_id)

    class ResponseStatusCode403UserTrialExpired(Check[InferenceContext]):
        def check(self, context: InferenceContext):
            is_user_trial_expired(
                context.model_id,
                context.result.status_code,
                context.result.json().get("message_id"),
            )

    def __init__(self):
        super().__init__(
            [
                # The ordering of these checks is important!
                InferenceResponseChecks.ResponseStatusCode204(),
                InferenceResponseChecks.ResponseStatusCode400WCABadRequestModelId(),
                InferenceResponseChecks.ResponseStatusCode400(),
                InferenceResponseChecks.ResponseStatusCode403Cloudflare(),
                InferenceResponseChecks.ResponseStatusCode403UserTrialExpired(),
                InferenceResponseChecks.ResponseStatusCode403(),
            ]
        )


class ContentMatchContext:
    def __init__(self, model_id, result, is_multi_task_suggestion):
        self.model_id = model_id
        self.result = result
        self.is_multi_task_suggestion = is_multi_task_suggestion


class ContentMatchResponseChecks(Checks[ContentMatchContext]):
    class ResponseStatusCode204(Check[ContentMatchContext]):
        def check(self, context: ContentMatchContext):
            if context.result.status_code == 204:
                raise WcaEmptyResponse(model_id=context.model_id)

    class ResponseStatusCode400WCABadRequestModelId(Check[ContentMatchContext]):
        def check(self, context: ContentMatchContext):
            if context.result.status_code == 400:
                payload_json = context.result.json()
                if isinstance(payload_json, dict):
                    payload_error = payload_json.get("error")
                    if (
                        payload_error
                        and "bad request" in payload_error.lower()
                        and "('body', 'model_id')" in payload_error.lower()
                    ):
                        raise WcaInvalidModelId(model_id=context.model_id)

    class ResponseStatusCode400(Check[ContentMatchContext]):
        def check(self, context: ContentMatchContext):
            if context.result.status_code == 400:
                raise WcaBadRequest(model_id=context.model_id, json_response=context.result.json())

    class ResponseStatusCode403(Check[ContentMatchContext]):
        def check(self, context: ContentMatchContext):
            if context.result.status_code == 403:
                raise WcaInvalidModelId(model_id=context.model_id)

    class ResponseStatusCode403Cloudflare(Check[InferenceContext]):
        def check(self, context: ContentMatchContext):
            if context.result.status_code == 403:
                text = context.result.text
                if text and "cloudflare" in text.lower():
                    raise WcaCloudflareRejection(model_id=context.model_id)

    class ResponseStatusCode403UserTrialExpired(Check[InferenceContext]):
        def check(self, context: ContentMatchContext):
            is_user_trial_expired(
                context.model_id,
                context.result.status_code,
                context.result.json().get("message_id"),
            )

    def __init__(self):
        super().__init__(
            [
                # The ordering of these checks is important!
                ContentMatchResponseChecks.ResponseStatusCode204(),
                ContentMatchResponseChecks.ResponseStatusCode400WCABadRequestModelId(),
                ContentMatchResponseChecks.ResponseStatusCode400(),
                ContentMatchResponseChecks.ResponseStatusCode403Cloudflare(),
                ContentMatchResponseChecks.ResponseStatusCode403UserTrialExpired(),
                ContentMatchResponseChecks.ResponseStatusCode403(),
            ]
        )


def is_user_trial_expired(model_id, result_code, message_id):
    if result_code == 403 and "WCA-0001-E" == message_id:
        raise WcaUserTrialExpired(model_id=model_id)
