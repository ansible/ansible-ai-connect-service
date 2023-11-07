from abc import abstractmethod
from typing import Generic, TypeVar

from .exceptions import WcaCloudflareRejection, WcaEmptyResponse, WcaInvalidModelId

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

    class ResponseStatusCode400SingleTask(Check[InferenceContext]):
        def check(self, context: InferenceContext):
            if context.is_multi_task_prompt:
                return
            if context.result.status_code == 400:
                raise WcaInvalidModelId(model_id=context.model_id)

    class ResponseStatusCode400MultiTask(Check[InferenceContext]):
        def check(self, context: InferenceContext):
            if not context.is_multi_task_prompt:
                return
            if context.result.status_code == 400:
                if "Failed to preprocess the prompt" in context.result.json()["detail"]:
                    raise WcaEmptyResponse(model_id=context.model_id)
                else:
                    raise WcaInvalidModelId(model_id=context.model_id)

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

    def __init__(self):
        super().__init__(
            [
                # The ordering of these checks is important!
                InferenceResponseChecks.ResponseStatusCode204(),
                InferenceResponseChecks.ResponseStatusCode400SingleTask(),
                InferenceResponseChecks.ResponseStatusCode400MultiTask(),
                InferenceResponseChecks.ResponseStatusCode403Cloudflare(),
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

    class ResponseStatusCode400SingleTask(Check[ContentMatchContext]):
        def check(self, context: ContentMatchContext):
            if context.is_multi_task_suggestion:
                return
            if context.result.status_code == 400:
                raise WcaInvalidModelId(model_id=context.model_id)

    class ResponseStatusCode400MultiTask(Check[ContentMatchContext]):
        def check(self, context: ContentMatchContext):
            if not context.is_multi_task_suggestion:
                return
            if context.result.status_code == 400:
                raise WcaInvalidModelId(model_id=context.model_id)

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

    def __init__(self):
        super().__init__(
            [
                # The ordering of these checks is important!
                ContentMatchResponseChecks.ResponseStatusCode204(),
                ContentMatchResponseChecks.ResponseStatusCode400SingleTask(),
                ContentMatchResponseChecks.ResponseStatusCode400MultiTask(),
                ContentMatchResponseChecks.ResponseStatusCode403Cloudflare(),
                ContentMatchResponseChecks.ResponseStatusCode403(),
            ]
        )
