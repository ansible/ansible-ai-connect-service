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
import sys
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Generic, Optional, TypeVar, cast

import backoff
import requests
from ansible_anonymizer import anonymizer
from django.apps import apps
from django.conf import settings
from django_prometheus.conf import NAMESPACE
from health_check.exceptions import ServiceUnavailable
from prometheus_client import Counter, Histogram
from requests.exceptions import HTTPError

from ansible_ai_connect.ai.api.exceptions import FeatureNotAvailable
from ansible_ai_connect.ai.api.formatter import (
    get_task_names_from_prompt,
    strip_task_preamble_from_multi_task_prompt,
    unify_prompt_ending,
)
from ansible_ai_connect.ai.api.model_pipelines.exceptions import (
    ModelTimeoutError,
    WcaCodeMatchFailure,
    WcaInferenceFailure,
    WcaRequestIdCorrelationFailure,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    PIPELINE_PARAMETERS,
    PIPELINE_RETURN,
    CompletionsParameters,
    CompletionsResponse,
    ContentMatchParameters,
    ContentMatchResponse,
    MetaData,
    ModelPipeline,
    ModelPipelineCompletions,
    ModelPipelineContentMatch,
    ModelPipelinePlaybookExplanation,
    ModelPipelinePlaybookGeneration,
    ModelPipelineRoleExplanation,
    ModelPipelineRoleGeneration,
    PlaybookExplanationParameters,
    PlaybookExplanationResponse,
    PlaybookGenerationParameters,
    PlaybookGenerationResponse,
    RoleExplanationParameters,
    RoleExplanationResponse,
    RoleGenerationParameters,
    RoleGenerationResponse,
)
from ansible_ai_connect.ai.api.model_pipelines.wca.configuration_base import (
    WCABaseConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.wca.wca_utils import (
    ContentMatchResponseChecks,
    Context,
    InferenceResponseChecks,
)
from ansible_ai_connect.main.ssl_manager import (
    AllowBrokenSSLContextHTTPAdapter,
    ssl_manager,
)

if TYPE_CHECKING:
    from ansible_ai_connect.users.models import User
else:
    User = None

MODEL_MESH_HEALTH_CHECK_TOKENS = "tokens"

WCA_REQUEST_ID_HEADER = "X-Request-ID"

WCA_REQUEST_USER_UUID_HEADER = "X-Request-LightspeedUser"

# from django_prometheus.middleware.DEFAULT_LATENCY_BUCKETS
DEFAULT_LATENCY_BUCKETS = (
    0.01,
    0.025,
    0.05,
    0.075,
    0.1,
    0.25,
    0.5,
    0.75,
    1.0,
    2.5,
    5.0,
    7.5,
    10.0,
    25.0,
    50.0,
    75.0,
    float("inf"),
)

logger = logging.getLogger(__name__)

WCA_PIPELINE_CONFIGURATION = TypeVar("WCA_PIPELINE_CONFIGURATION", bound=WCABaseConfiguration)

wca_codegen_hist = Histogram(
    "wca_codegen_latency_seconds",
    "Histogram of WCA codegen API processing time",
    namespace=NAMESPACE,
    buckets=DEFAULT_LATENCY_BUCKETS,
)
wca_codematch_hist = Histogram(
    "wca_codematch_latency_seconds",
    "Histogram of WCA codematch API processing time",
    namespace=NAMESPACE,
    buckets=DEFAULT_LATENCY_BUCKETS,
)
wca_codegen_playbook_hist = Histogram(
    "wca_codegen_playbook_latency_seconds",
    "Histogram of WCA codegen-playbook API processing time",
    namespace=NAMESPACE,
    buckets=DEFAULT_LATENCY_BUCKETS,
)
wca_codegen_role_hist = Histogram(
    "wca_codegen_role_latency_seconds",
    "Histogram of WCA codegen-role API processing time",
    namespace=NAMESPACE,
    buckets=DEFAULT_LATENCY_BUCKETS,
)
wca_explain_playbook_hist = Histogram(
    "wca_explain_playbook_latency_seconds",
    "Histogram of WCA explain-playbook API processing time",
    namespace=NAMESPACE,
    buckets=DEFAULT_LATENCY_BUCKETS,
)
wca_explain_role_hist = Histogram(
    "wca_explain_role_latency_seconds",
    "Histogram of WCA explain-role API processing time",
    namespace=NAMESPACE,
    buckets=DEFAULT_LATENCY_BUCKETS,
)
ibm_cloud_identity_token_hist = Histogram(
    "wca_ibm_identity_token_latency_seconds",
    "Histogram of IBM Cloud identity token API processing time",
    namespace=NAMESPACE,
    buckets=DEFAULT_LATENCY_BUCKETS,
)
wca_codegen_retry_counter = Counter(
    "wca_codegen_retries",
    "Counter of WCA codegen API invocation retries",
    namespace=NAMESPACE,
)
wca_codematch_retry_counter = Counter(
    "wca_codematch_retries",
    "Counter of WCA codematch API invocation retries",
    namespace=NAMESPACE,
)
wca_codegen_playbook_retry_counter = Counter(
    "wca_codegen_playbook_retries",
    "Counter of WCA codegen-playbook API invocation retries",
    namespace=NAMESPACE,
)
wca_codegen_role_retry_counter = Counter(
    "wca_codegen_role_retries",
    "Counter of WCA codegen-role API invocation retries",
    namespace=NAMESPACE,
)
wca_explain_playbook_retry_counter = Counter(
    "wca_explain_playbook_retries",
    "Counter of WCA explain-playbook API invocation retries",
    namespace=NAMESPACE,
)
wca_explain_role_retry_counter = Counter(
    "wca_explain_role_retries",
    "Counter of WCA explain-role API invocation retries",
    namespace=NAMESPACE,
)
ibm_cloud_identity_token_retry_counter = Counter(
    "ibm_cloud_identity_token_retries",
    "Counter of IBM Cloud identity token API invocation retries",
    namespace=NAMESPACE,
)


class WcaTokenRequestException(ServiceUnavailable):
    """There was an error trying to get a WCA token."""


class WcaModelRequestException(ServiceUnavailable):
    """There was an error trying to invoke a WCA Model."""


class WCABaseMetaData(
    MetaData[WCA_PIPELINE_CONFIGURATION], Generic[WCA_PIPELINE_CONFIGURATION], metaclass=ABCMeta
):

    def __init__(self, config: WCA_PIPELINE_CONFIGURATION):
        super().__init__(config=config)
        # Use centralized SSL manager for all WCA requests
        self.session = ssl_manager.get_requests_session()

        # Ignore SSL errors with inference_url
        if not self.config.verify_ssl:
            self.session.mount(
                self.config.inference_url,
                AllowBrokenSSLContextHTTPAdapter(),
            )

        self.retries = self.config.retry_count
        i = self.config.timeout
        self._timeout = int(i) if i is not None else None

    def task_gen_timeout(self, task_count=1):
        return self._timeout * task_count if self._timeout else None

    @staticmethod
    def fatal_exception(exc) -> bool:
        """Determine if an exception is fatal or not"""
        if isinstance(exc, requests.RequestException):
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            # retry on server errors and client errors
            # with 429 status code (rate limited),
            # don't retry on other client errors
            return bool(status_code and (400 <= status_code < 500) and status_code != 429)
        else:
            # retry on all other errors (e.g. network)
            return False

    @staticmethod
    def on_backoff_ibm_cloud_identity_token(details):
        WCABasePipeline.log_backoff_exception(details)
        ibm_cloud_identity_token_retry_counter.inc()

    @abstractmethod
    def get_api_key(self, user) -> str:
        raise NotImplementedError


class WCABasePipeline(
    WCABaseMetaData,
    ModelPipeline[WCA_PIPELINE_CONFIGURATION, PIPELINE_PARAMETERS, PIPELINE_RETURN],
    Generic[WCA_PIPELINE_CONFIGURATION, PIPELINE_PARAMETERS, PIPELINE_RETURN],
    metaclass=ABCMeta,
):

    def __init__(self, config: WCA_PIPELINE_CONFIGURATION):
        super().__init__(config=config)

    def should_anonymize(self, request) -> bool:
        """Helper method to determine if anonymization should be applied.

        Args:
            request: The request object containing user and organization information

        Returns:
            bool: True if anonymization should be applied, False otherwise
        """
        if not self.config.enable_anonymization:
            return False

        # If user has no organization, apply anonymization by default
        if not request.user.organization:
            return True

        # Otherwise check organization's setting
        return request.user.organization.enable_anonymization is True

    def _prepare_request_headers(
        self, request_user: Optional[User], api_key: str, identifier: Optional[str]
    ) -> dict[str, Optional[str]]:
        """
        Helper method to extract user UUID and get request headers.
        """
        lightspeed_user_uuid_str: Optional[str] = None
        if request_user and hasattr(request_user, "uuid"):
            lightspeed_user_uuid_str = str(request_user.uuid)

        return self.get_request_headers(
            api_key, identifier, lightspeed_user_uuid=lightspeed_user_uuid_str
        )

    @staticmethod
    def log_backoff_exception(details):
        _, exc, _ = sys.exc_info()
        logger.info(str(exc))
        logger.info(
            f"Caught retryable error after {details['tries']} tries. "
            f"Waiting {details['wait']} more seconds then retrying..."
        )

    @staticmethod
    def on_backoff_inference(details):
        WCABasePipeline.log_backoff_exception(details)
        wca_codegen_retry_counter.inc()

    @staticmethod
    def on_backoff_codematch(details):
        WCABasePipeline.log_backoff_exception(details)
        wca_codematch_retry_counter.inc()

    @staticmethod
    def on_backoff_codegen_playbook(details):
        WCABasePipeline.log_backoff_exception(details)
        wca_codegen_playbook_retry_counter.inc()

    @staticmethod
    def on_backoff_codegen_role(details):
        WCABasePipeline.log_backoff_exception(details)
        wca_codegen_role_retry_counter.inc()

    @staticmethod
    def on_backoff_explain_playbook(details):
        WCABasePipeline.log_backoff_exception(details)
        wca_explain_playbook_retry_counter.inc()

    @staticmethod
    def on_backoff_explain_role(details):
        WCABasePipeline.log_backoff_exception(details)
        wca_explain_role_retry_counter.inc()

    @abstractmethod
    def get_request_headers(
        self, api_key: str, identifier: Optional[str], lightspeed_user_uuid: Optional[str] = None
    ) -> dict[str, Optional[str]]:
        raise NotImplementedError


class WCABaseCompletionsPipeline(
    WCABasePipeline[WCA_PIPELINE_CONFIGURATION, CompletionsParameters, CompletionsResponse],
    ModelPipelineCompletions[WCA_PIPELINE_CONFIGURATION],
    Generic[WCA_PIPELINE_CONFIGURATION],
    metaclass=ABCMeta,
):

    def __init__(self, config: WCA_PIPELINE_CONFIGURATION):
        super().__init__(config=config)

    def invoke(self, params: CompletionsParameters) -> CompletionsResponse:
        request = params.request
        model_id = params.model_id
        model_input = params.model_input
        suggestion_id = params.suggestion_id
        logger.debug(f"Input prompt: {model_input}")

        prompt = model_input.get("instances", [{}])[0].get("prompt", "")
        context = model_input.get("instances", [{}])[0].get("context", "")

        # WCA codegen fails if a multitask prompt includes the task preamble
        # https://github.com/rh-ibm-synergy/wca-feedback/issues/34
        prompt = strip_task_preamble_from_multi_task_prompt(prompt)

        prompt = unify_prompt_ending(prompt)

        try:
            api_key = self.get_api_key(request.user)
            model_id = self.get_model_id(request.user, model_id)

            headers = self._prepare_request_headers(request.user, api_key, suggestion_id)

            if self.should_anonymize(request):
                logger.debug("Anonymizing prompt and context")
                context = anonymizer.anonymize_struct(context)
                prompt = "#".join(anonymizer.anonymize_struct(prompt.split("#")))

            result = self.infer_from_parameters(model_id, context, prompt, suggestion_id, headers)

            response = result.json()
            response["model_id"] = model_id
            logger.debug(f"Inference API response: {response}")
            return response

        except requests.exceptions.Timeout:
            raise ModelTimeoutError(model_id=model_id)

    def infer_from_parameters(self, model_id, context, prompt, suggestion_id=None, headers=None):
        data = {
            "model_id": model_id,
            "prompt": f"{context}{prompt}",
        }
        logger.debug(f"Inference API request payload: {json.dumps(data)}")

        task_count = len(get_task_names_from_prompt(prompt))
        prediction_url = f"{self.config.inference_url}/v1/wca/codegen/ansible"

        @backoff.on_exception(
            backoff.expo,
            Exception,
            max_tries=self.retries + 1,
            giveup=self.fatal_exception,
            on_backoff=self.on_backoff_inference,
        )
        @wca_codegen_hist.time()
        def post_request():
            return self.session.post(
                prediction_url,
                headers=headers,
                json=data,
                timeout=self.task_gen_timeout(task_count),
            )

        try:
            response = post_request()

            x_request_id = response.headers.get(WCA_REQUEST_ID_HEADER)
            if suggestion_id and x_request_id:
                # request/payload suggestion_id is a UUID not a string whereas
                # HTTP headers are strings.
                if x_request_id != str(suggestion_id):
                    raise WcaRequestIdCorrelationFailure(
                        model_id=model_id, x_request_id=x_request_id
                    )

            context = Context(model_id, response, task_count > 1)
            InferenceResponseChecks().run_checks(context)
            response.raise_for_status()

        except HTTPError as e:
            logger.error(f"WCA inference failed for suggestion {suggestion_id} due to {e}.")
            raise WcaInferenceFailure(model_id=model_id)

        return response


class WCABaseContentMatchPipeline(
    WCABasePipeline[WCA_PIPELINE_CONFIGURATION, ContentMatchParameters, ContentMatchResponse],
    ModelPipelineContentMatch[WCA_PIPELINE_CONFIGURATION],
    Generic[WCA_PIPELINE_CONFIGURATION],
    metaclass=ABCMeta,
):

    def __init__(self, config: WCA_PIPELINE_CONFIGURATION):
        super().__init__(config=config)

    @abstractmethod
    def get_codematch_headers(self, api_key: str) -> dict[str, str]:
        raise NotImplementedError

    def invoke(self, params: ContentMatchParameters) -> ContentMatchResponse:
        request = params.request
        model_input = params.model_input
        model_id = params.model_id
        logger.debug(f"Input prompt: {model_input}")
        self._search_url = f"{self.config.inference_url}/v1/wca/codematch/ansible"

        suggestions = model_input.get("suggestions", "")
        model_id = self.get_model_id(request.user, model_id)

        data = {
            "model_id": model_id,
            "input": suggestions,
        }

        try:
            api_key = self.get_api_key(request.user)
            headers = self.get_codematch_headers(api_key)
            suggestion_count = len(suggestions)

            @backoff.on_exception(
                backoff.expo,
                Exception,
                max_tries=self.retries + 1,
                giveup=self.fatal_exception,
                on_backoff=self.on_backoff_codematch,
            )
            @wca_codematch_hist.time()
            def post_request() -> requests.Response:
                return self.session.post(
                    self._search_url,
                    headers=headers,
                    json=data,
                    timeout=self.task_gen_timeout(suggestion_count),
                )

            result: requests.Response = post_request()
            context = Context(model_id, result, suggestion_count > 1)
            ContentMatchResponseChecks().run_checks(context)
            result.raise_for_status()

            response = result.json()
            logger.debug(f"Codematch API response: {response}")

            return model_id, response

        except HTTPError:
            raise WcaCodeMatchFailure(model_id=model_id)

        except requests.exceptions.ReadTimeout:
            raise ModelTimeoutError(model_id=model_id)


class WCABasePlaybookGenerationPipeline(
    WCABasePipeline[
        WCA_PIPELINE_CONFIGURATION, PlaybookGenerationParameters, PlaybookGenerationResponse
    ],
    ModelPipelinePlaybookGeneration[WCA_PIPELINE_CONFIGURATION],
    Generic[WCA_PIPELINE_CONFIGURATION],
    metaclass=ABCMeta,
):

    def __init__(self, config: WCA_PIPELINE_CONFIGURATION):
        super().__init__(config=config)

    def invoke(self, params: PlaybookGenerationParameters) -> PlaybookGenerationResponse:
        request = params.request
        text = params.text
        custom_prompt = params.custom_prompt
        create_outline = params.create_outline
        outline = params.outline
        model_id = params.model_id
        generation_id = params.generation_id

        api_key = self.get_api_key(request.user)
        model_id = self.get_model_id(request.user, model_id)

        headers = self._prepare_request_headers(request.user, api_key, generation_id)

        data = {
            "model_id": model_id,
            "text": text,
            "create_outline": create_outline,
        }

        if outline:
            data["outline"] = outline
        if custom_prompt:
            if not custom_prompt.endswith("\n"):
                custom_prompt = f"{custom_prompt}\n"
            data["custom_prompt"] = custom_prompt

        # Apply anonymization if enabled for the organization
        if self.should_anonymize(request):
            logger.debug("Anonymizing text and custom prompt")
            data["text"] = anonymizer.anonymize_struct(data["text"])
            if custom_prompt:
                data["custom_prompt"] = anonymizer.anonymize_struct(data["custom_prompt"])

        @backoff.on_exception(
            backoff.expo,
            Exception,
            max_tries=self.retries + 1,
            giveup=self.fatal_exception,
            on_backoff=self.on_backoff_codegen_playbook,
        )
        @wca_codegen_playbook_hist.time()
        def post_request():
            return self.session.post(
                f"{self.config.inference_url}/v1/wca/codegen/ansible/playbook",
                headers=headers,
                json=data,
            )

        result = post_request()

        x_request_id = result.headers.get(WCA_REQUEST_ID_HEADER)
        if generation_id and x_request_id:
            # request/payload suggestion_id is a UUID not a string whereas
            # HTTP headers are strings.
            if x_request_id != str(generation_id):
                raise WcaRequestIdCorrelationFailure(model_id=model_id, x_request_id=x_request_id)

        context = Context(model_id, result, False)
        InferenceResponseChecks().run_checks(context)
        result.raise_for_status()

        response = json.loads(result.text)

        playbook = response["playbook"]
        outline = response["outline"]
        warnings = response["warnings"] if "warnings" in response else []

        from ansible_ai_connect.ai.apps import AiConfig

        ai_config = cast(AiConfig, apps.get_app_config("ai"))
        if ansible_lint_caller := ai_config.get_ansible_lint_caller():
            playbook = ansible_lint_caller.run_linter(playbook)

        return playbook, outline, warnings


class WCABaseRoleGenerationPipeline(
    WCABasePipeline[WCA_PIPELINE_CONFIGURATION, RoleGenerationParameters, RoleGenerationResponse],
    ModelPipelineRoleGeneration[WCA_PIPELINE_CONFIGURATION],
    Generic[WCA_PIPELINE_CONFIGURATION],
    metaclass=ABCMeta,
):

    def __init__(self, config: WCA_PIPELINE_CONFIGURATION):
        super().__init__(config=config)

    def invoke(self, params: RoleGenerationParameters) -> RoleGenerationResponse:
        if not settings.ANSIBLE_AI_ENABLE_ROLE_GEN_ENDPOINT:
            raise FeatureNotAvailable

        request = params.request
        name = params.name
        text = params.text
        create_outline = params.create_outline
        outline = params.outline
        model_id = params.model_id
        generation_id = params.generation_id

        api_key = self.get_api_key(request.user)
        model_id = self.get_model_id(request.user, model_id)

        headers = self._prepare_request_headers(request.user, api_key, generation_id)

        data = {
            "model_id": model_id,
            "text": text,
            "create_outline": create_outline,
        }
        if name:
            data["name"] = name
        if outline:
            data["outline"] = outline

        # Apply anonymization if enabled for the organization
        if self.should_anonymize(request):
            logger.debug("Anonymizing text and name")
            data["text"] = anonymizer.anonymize_struct(data["text"])
            if name:
                data["name"] = anonymizer.anonymize_struct(data["name"])

        @backoff.on_exception(
            backoff.expo,
            Exception,
            max_tries=self.retries + 1,
            giveup=self.fatal_exception,
            on_backoff=self.on_backoff_codegen_role,
        )
        @wca_codegen_role_hist.time()
        def post_request():
            return self.session.post(
                f"{self.config.inference_url}/v1/wca/codegen/ansible/roles",
                headers=headers,
                json=data,
            )

        result = post_request()

        x_request_id = result.headers.get(WCA_REQUEST_ID_HEADER)
        if generation_id and x_request_id:
            # request/payload suggestion_id is a UUID not a string whereas
            # HTTP headers are strings.
            if x_request_id != str(generation_id):
                raise WcaRequestIdCorrelationFailure(model_id=model_id, x_request_id=x_request_id)

        context = Context(model_id, result, False)
        InferenceResponseChecks().run_checks(context)
        result.raise_for_status()

        response = json.loads(result.text)

        name = response["name"]
        files = response["files"]
        outline = response["outline"]
        warnings = response["warnings"] if "warnings" in response else []

        from ansible_ai_connect.ai.apps import AiConfig

        ai_config = cast(AiConfig, apps.get_app_config("ai"))
        if ansible_lint_caller := ai_config.get_ansible_lint_caller():
            for file in files:
                if file["file_type"] != "task":
                    continue
                file["content"] = ansible_lint_caller.run_linter(file["content"])

        return name, files, outline, warnings


class WCABasePlaybookExplanationPipeline(
    WCABasePipeline[
        WCA_PIPELINE_CONFIGURATION, PlaybookExplanationParameters, PlaybookExplanationResponse
    ],
    ModelPipelinePlaybookExplanation[WCA_PIPELINE_CONFIGURATION],
    Generic[WCA_PIPELINE_CONFIGURATION],
    metaclass=ABCMeta,
):

    def __init__(self, config: WCA_PIPELINE_CONFIGURATION):
        super().__init__(config=config)

    def invoke(self, params: PlaybookExplanationParameters) -> PlaybookExplanationResponse:
        request = params.request
        content = params.content
        custom_prompt = params.custom_prompt
        model_id = params.model_id
        explanation_id = params.explanation_id

        api_key = self.get_api_key(request.user)
        model_id = self.get_model_id(request.user, model_id)

        headers = self._prepare_request_headers(request.user, api_key, explanation_id)

        data = {
            "model_id": model_id,
            "playbook": content,
        }
        if custom_prompt:
            if not custom_prompt.endswith("\n"):
                custom_prompt = f"{custom_prompt}\n"
            data["custom_prompt"] = custom_prompt

        # Apply anonymization if enabled for the organization
        if self.should_anonymize(request):
            logger.debug("Anonymizing playbook content and custom prompt")
            data["playbook"] = anonymizer.anonymize_struct(data["playbook"])
            if custom_prompt:
                data["custom_prompt"] = anonymizer.anonymize_struct(data["custom_prompt"])

        @backoff.on_exception(
            backoff.expo,
            Exception,
            max_tries=self.retries + 1,
            giveup=self.fatal_exception,
            on_backoff=self.on_backoff_explain_playbook,
        )
        @wca_explain_playbook_hist.time()
        def post_request():
            return self.session.post(
                f"{self.config.inference_url}/v1/wca/explain/ansible/playbook",
                headers=headers,
                json=data,
            )

        result = post_request()

        x_request_id = result.headers.get(WCA_REQUEST_ID_HEADER)
        if explanation_id and x_request_id:
            # request/payload suggestion_id is a UUID not a string whereas
            # HTTP headers are strings.
            if x_request_id != str(explanation_id):
                raise WcaRequestIdCorrelationFailure(model_id=model_id, x_request_id=x_request_id)

        context = Context(model_id, result, False)
        InferenceResponseChecks().run_checks(context)
        result.raise_for_status()

        response = json.loads(result.text)
        return response["explanation"]


class WCABaseRoleExplanationPipeline(
    WCABasePipeline[WCA_PIPELINE_CONFIGURATION, RoleExplanationParameters, RoleExplanationResponse],
    ModelPipelineRoleExplanation[WCA_PIPELINE_CONFIGURATION],
    Generic[WCA_PIPELINE_CONFIGURATION],
    metaclass=ABCMeta,
):

    def __init__(self, config: WCA_PIPELINE_CONFIGURATION):
        super().__init__(config=config)

    def invoke(self, params: RoleExplanationParameters) -> RoleExplanationResponse:
        request = params.request
        files = params.files
        model_id = params.model_id
        explanation_id = params.explanation_id

        api_key = self.get_api_key(request.user)
        model_id = self.get_model_id(request.user, model_id)

        headers = self._prepare_request_headers(request.user, api_key, explanation_id)

        data = {
            "role_name": params.role_name,
            "model_id": model_id,
            "files": files,
        }

        # Apply anonymization if enabled for the organization
        if self.should_anonymize(request):
            logger.debug("Anonymizing role name and files content")
            data["role_name"] = anonymizer.anonymize_struct(data["role_name"])
            data["files"] = anonymizer.anonymize_struct(data["files"])

        @backoff.on_exception(
            backoff.expo,
            Exception,
            max_tries=self.retries + 1,
            giveup=self.fatal_exception,
            on_backoff=self.on_backoff_explain_role,
        )
        @wca_explain_role_hist.time()
        def post_request():
            return self.session.post(
                f"{self.config.inference_url}/v1/wca/codegen/ansible/roles/explain",
                headers=headers,
                json=data,
            )

        result = post_request()

        x_request_id = result.headers.get(WCA_REQUEST_ID_HEADER)
        if explanation_id and x_request_id:
            # request/payload suggestion_id is a UUID not a string whereas
            # HTTP headers are strings.
            if x_request_id != str(explanation_id):
                raise WcaRequestIdCorrelationFailure(model_id=model_id, x_request_id=x_request_id)

        context = Context(model_id, result, False)
        InferenceResponseChecks().run_checks(context)
        result.raise_for_status()

        response = json.loads(result.text)
        return response["explanation"]
