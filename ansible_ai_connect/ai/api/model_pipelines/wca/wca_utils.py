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
import re
from abc import abstractmethod
from typing import Generic, TypeVar

import requests

from ansible_ai_connect.ai.api.model_pipelines.exceptions import (
    WcaBadRequest,
    WcaCloudflareRejection,
    WcaEmptyResponse,
    WcaHAPFilterRejection,
    WcaInferenceFailure,
    WcaInstanceDeleted,
    WcaInvalidModelId,
    WcaTokenFailureApiKeyError,
    WcaUserTrialExpired,
    WcaValidationFailure,
)

T = TypeVar("T")

logger = logging.getLogger(__name__)


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
            try:
                check.check(context)
            except Exception:
                logger.error(
                    f"WCA request failed with {context.result.status_code}. "
                    f"Content-Type:{context.result.headers.get('Content-Type')}, "
                    f"Content:{context.result.content}"
                )
                raise


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


class Context:
    def __init__(self, model_id, result: requests.Response, is_multi_task_prompt):
        self.model_id = model_id
        self.result = result
        self.is_multi_task_prompt = is_multi_task_prompt


class ResponseStatusCode204(Check[Context]):
    def check(self, context: Context):
        if context.result.status_code == 204:
            raise WcaEmptyResponse(model_id=context.model_id)


class ResponseStatusCode400WCABadRequestModelId(Check[Context]):
    def check(self, context: Context):
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


class ResponseStatusCode400WCAHAPFilter(Check[Context]):
    def check(self, context: Context):
        if context.result.status_code == 400:
            payload_json = context.result.json()
            if isinstance(payload_json, dict):
                payload_detail = payload_json.get("detail")
                if (
                    payload_detail
                    and "our filters detected a potential problem with entities in your input"
                    in payload_detail.lower()
                ):
                    raise WcaHAPFilterRejection(
                        model_id=context.model_id, json_response=context.result.json()
                    )


class ResponseStatusCode400(Check[Context]):
    def check(self, context: Context):
        if context.result.status_code == 400:
            raise WcaBadRequest(model_id=context.model_id, json_response=context.result.json())


class ResponseStatusCode403(Check[Context]):
    def check(self, context: Context):
        if context.result.status_code == 403:
            raise WcaInvalidModelId(model_id=context.model_id)


class ResponseStatusCode403Cloudflare(Check[Context]):
    def check(self, context: Context):
        if context.result.status_code == 403:
            text = context.result.text
            if text and "cloudflare" in text.lower():
                raise WcaCloudflareRejection(model_id=context.model_id)


class ResponseStatusCode403UserTrialExpired(Check[Context]):

    def check(self, context: Context):
        if context.result.status_code == 403:
            payload_json = context.result.json()
            if isinstance(payload_json, dict):
                payload_message_id = payload_json.get("message_id")
                if payload_message_id and "wca-0001-e" in payload_message_id.lower():
                    raise WcaUserTrialExpired(model_id=context.model_id)


class ResponseStatusCode404WCABadRequestModelId(Check[Context]):
    def check(self, context: Context):
        if context.result.status_code == 404:
            content_type = context.result.headers.get("Content-Type")
            if content_type is not None and content_type.lower() == "application/json":
                payload_json = context.result.json()
                if isinstance(payload_json, dict):
                    payload_detail = payload_json.get("detail")
                    if payload_detail and "wml api call failed" in payload_detail.lower():
                        raise WcaInvalidModelId(model_id=context.model_id)


class ResponseStatusCode404WCAInstanceDeleted(Check[Context]):
    def check(self, context: Context):
        if context.result.status_code == 404:
            payload_json = context.result.json()
            if isinstance(payload_json, dict):
                payload_detail = payload_json.get("detail")
                if payload_detail and re.search(
                    r"The WCA instance \S+ has been deleted", payload_detail
                ):
                    raise WcaInstanceDeleted(model_id=context.model_id)


class ResponseStatusCode404(Check[Context]):
    def check(self, context: Context):
        if context.result.status_code == 404:
            raise WcaInferenceFailure(model_id=context.model_id)


class ResponseStatusCode422WCAValidationFailure(Check[Context]):
    def check(self, context: Context):
        if context.result.status_code == 422:
            payload_json = context.result.json()
            if isinstance(payload_json, dict):
                payload_detail = payload_json.get("detail")
                if payload_detail and "validation failed" in payload_detail.lower():
                    raise WcaValidationFailure(
                        model_id=context.model_id, json_response=context.result.json()
                    )


class InferenceResponseChecks(Checks[Context]):

    def __init__(self):
        super().__init__(
            [
                # The ordering of these checks is important!
                ResponseStatusCode204(),
                ResponseStatusCode400WCABadRequestModelId(),
                ResponseStatusCode400WCAHAPFilter(),
                ResponseStatusCode400(),
                ResponseStatusCode403Cloudflare(),
                ResponseStatusCode403UserTrialExpired(),
                ResponseStatusCode403(),
                ResponseStatusCode404WCABadRequestModelId(),
                ResponseStatusCode404WCAInstanceDeleted(),
                ResponseStatusCode404(),
                ResponseStatusCode422WCAValidationFailure(),
            ]
        )


class ContentMatchResponseChecks(Checks[Context]):

    def __init__(self):
        super().__init__(
            [
                # The ordering of these checks is important!
                ResponseStatusCode204(),
                ResponseStatusCode400WCABadRequestModelId(),
                ResponseStatusCode400(),
                ResponseStatusCode403Cloudflare(),
                ResponseStatusCode403UserTrialExpired(),
                ResponseStatusCode403(),
                ResponseStatusCode404WCABadRequestModelId(),
                ResponseStatusCode404WCAInstanceDeleted(),
            ]
        )
