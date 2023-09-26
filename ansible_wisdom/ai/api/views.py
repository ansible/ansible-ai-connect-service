import json
import logging
import time
from enum import Enum
from string import Template

import yaml
from ai.api.model_client.wca_client import WcaBadRequest
from ansible_anonymizer import anonymizer
from django.apps import apps
from django.conf import settings
from django_prometheus.conf import NAMESPACE
from drf_spectacular.utils import OpenApiResponse, extend_schema
from prometheus_client import Counter, Histogram
from rest_framework import serializers
from rest_framework import status as rest_framework_status
from rest_framework.exceptions import APIException
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from users.models import User
from yaml.error import MarkedYAMLError

from .. import search as ai_search
from ..feature_flags import FeatureFlags, WisdomFlags
from . import formatter as fmtr
from .data.data_model import APIPayload, ModelMeshPayload
from .model_client.exceptions import ModelTimeoutError
from .permissions import AcceptedTermsPermission
from .serializers import (
    AnsibleContentFeedback,
    AttributionRequestSerializer,
    AttributionResponseSerializer,
    CompletionRequestSerializer,
    CompletionResponseSerializer,
    FeedbackRequestSerializer,
    InlineSuggestionFeedback,
    IssueFeedback,
    SentimentFeedback,
    SuggestionQualityFeedback,
)
from .utils.segment import send_segment_event

logger = logging.getLogger(__name__)

feature_flags = FeatureFlags()

completions_hist = Histogram(
    'model_prediction_latency_seconds',
    "Histogram of model prediction processing time",
    namespace=NAMESPACE,
)
completions_return_code = Counter(
    'model_prediction_return_code', 'The return code of model prediction requests', ['code']
)
attribution_encoding_hist = Histogram(
    'model_attribution_encoding_latency_seconds',
    "Histogram of model attribution encoding processing time",
    namespace=NAMESPACE,
)
attribution_search_hist = Histogram(
    'model_attribution_search_latency_seconds',
    "Histogram of model attribution search processing time",
    namespace=NAMESPACE,
)
preprocess_hist = Histogram(
    'preprocessing_latency_seconds',
    "Histogram of pre-processing time",
    namespace=NAMESPACE,
)
postprocess_hist = Histogram(
    'postprocessing_latency_seconds',
    "Histogram of post-processing time",
    namespace=NAMESPACE,
)
process_error_count = Counter(
    'process_error', "Error counts at pre-process/prediction/post-process stages", ['stage']
)

STRIP_YAML_LINE = '---\n'


class BaseWisdomAPIException(APIException):
    def __init__(self, *args, **kwargs):
        completions_return_code.labels(code=self.status_code).inc()
        super().__init__(*args, **kwargs)


class PostprocessException(BaseWisdomAPIException):
    status_code = 204
    error_type = 'postprocess_error'


class ModelTimeoutException(BaseWisdomAPIException):
    status_code = 204
    error_type = 'model_timeout'


class WcaBadRequestException(BaseWisdomAPIException):
    status_code = 400
    default_detail = {"message": "Bad request for WCA completion"}


class ServiceUnavailable(BaseWisdomAPIException):
    status_code = 503
    default_detail = {"message": "An error occurred attempting to complete the request"}


class InternalServerError(BaseWisdomAPIException):
    status_code = 500
    default_detail = {"message": "An error occurred attempting to complete the request"}


class CompletionsPromptType(str, Enum):
    MULTITASK = "MULTITASK"
    SINGLETASK = "SINGLETASK"


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


class Completions(APIView):
    """
    Returns inline code suggestions based on a given Ansible editor context.
    """

    from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
    from rest_framework import permissions

    permission_classes = [
        permissions.IsAuthenticated,
        IsAuthenticatedOrTokenHasScope,
        AcceptedTermsPermission,
    ]
    required_scopes = ['read', 'write']

    throttle_cache_key_suffix = '_completions'

    @extend_schema(
        request=CompletionRequestSerializer,
        responses={
            200: CompletionResponseSerializer,
            204: OpenApiResponse(description='Empty response'),
            400: OpenApiResponse(description='Bad Request'),
            401: OpenApiResponse(description='Unauthorized'),
            429: OpenApiResponse(description='Request was throttled'),
            503: OpenApiResponse(description='Service Unavailable'),
        },
        summary="Inline code suggestions",
    )
    def post(self, request) -> Response:
        # Here `request` is a DRF wrapper around Django's original
        # WSGIRequest object.  It holds the original as
        # `self._request`, and that's the one we need to modify to
        # make this available to the middleware.
        request._request._suggestion_id = request.data.get('suggestionId')

        request_serializer = CompletionRequestSerializer(
            data=request.data, context={'request': request}
        )
        try:
            request_serializer.is_valid(raise_exception=True)
            request._request._suggestion_id = str(request_serializer.validated_data['suggestionId'])
        except Exception as exc:
            process_error_count.labels(stage='request_serialization_validation').inc()
            logger.warn(f'failed to validate request:\nException:\n{exc}')
            raise exc
        payload = APIPayload(**request_serializer.validated_data)
        payload.userId = request.user.uuid
        model_mesh_client, model_name = get_model_client(apps.get_app_config("ai"), request.user)
        # We have a little inconsistency of the "model" term throughout the application:
        # - FeatureFlags use 'model_name'
        # - ModelMeshClient uses 'model_id'
        # - Public completion API uses 'model'
        # - Segment Events use 'modelName'
        model_id = model_name or payload.model

        try:
            start_time = time.time()
            payload.context, payload.prompt, original_indent = self.preprocess(
                payload.context, payload.prompt
            )
        except Exception as exc:
            process_error_count.labels(stage='pre-processing').inc()
            # return the original prompt, context
            logger.error(
                f'failed to preprocess:\n{payload.context}{payload.prompt}\nException:\n{exc}'
            )
            message = (
                'Request contains invalid prompt'
                if isinstance(exc, fmtr.InvalidPromptException)
                else 'Request contains invalid yaml'
            )
            return Response({'message': message}, status=400)
        finally:
            duration = round((time.time() - start_time) * 1000, 2)
            preprocess_hist.observe(duration / 1000)  # millisec to seconds

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
        except ModelTimeoutError as exc:
            exception = exc
            logger.warn(
                f"model timed out after {settings.ANSIBLE_AI_MODEL_MESH_API_TIMEOUT} seconds"
                f" for suggestion {payload.suggestionId}"
            )
            raise ModelTimeoutException
        except WcaBadRequest as exc:
            exception = exc
            logger.exception(f"bad request for completion for suggestion {payload.suggestionId}")
            raise WcaBadRequestException
        except Exception as exc:
            exception = exc
            logger.exception(f"error requesting completion for suggestion {payload.suggestionId}")
            raise ServiceUnavailable
        finally:
            process_error_count.labels(stage='prediction').inc()
            duration = round((time.time() - start_time) * 1000, 2)
            completions_hist.observe(duration / 1000)  # millisec back to seconds
            value_template = Template("{{ _${variable_name}_ }}")
            ano_predictions = anonymizer.anonymize_struct(
                predictions, value_template=value_template
            )
            event = {
                "duration": duration,
                "exception": exception is not None,
                "problem": None if exception is None else exception.__class__.__name__,
                "request": data,
                "response": ano_predictions,
                "suggestionId": str(payload.suggestionId),
            }
            send_segment_event(event, "prediction", request.user)

        logger.debug(
            f"response from inference for suggestion id {payload.suggestionId}:\n{predictions}"
        )
        postprocessed_predictions = None
        try:
            start_time = time.time()
            postprocessed_predictions, tasks_results = self.postprocess(
                ano_predictions,
                payload.prompt,
                payload.context,
                request.user,
                payload.suggestionId,
                indent=original_indent,
            )
        except Exception:
            process_error_count.labels(stage='post-processing').inc()
            logger.exception(
                f"error postprocessing prediction for suggestion {payload.suggestionId}"
            )
            raise PostprocessException
        finally:
            duration = round((time.time() - start_time) * 1000, 2)
            postprocess_hist.observe(duration / 1000)  # millisec to seconds

        logger.debug(
            f"response from postprocess for "
            f"suggestion id {payload.suggestionId}:\n{postprocessed_predictions}"
        )
        try:
            response_data = {
                "predictions": postprocessed_predictions["predictions"],
                "model": predictions['model_id'],
                "suggestionId": payload.suggestionId,
            }
            response_serializer = CompletionResponseSerializer(data=response_data)
            response_serializer.is_valid(raise_exception=True)
        except Exception:
            process_error_count.labels(stage='response_serialization_validation').inc()
            logger.exception(
                f"error serializing final response for suggestion {payload.suggestionId}"
            )
            raise InternalServerError
        completions_return_code.labels(code=200).inc()
        response = Response(response_data, status=200)

        # add fields for telemetry only, not response data
        # Note: Currently we return an array of predictions, but there's only ever one.
        # The tasks array added to the completion event is representative of the first (only)
        # entry in the predictions array
        response.tasks = tasks_results
        response.promptType = (
            CompletionsPromptType.MULTITASK.value
            if fmtr.is_multi_task_prompt(payload.prompt)
            else CompletionsPromptType.SINGLETASK.value
        )
        return response

    def preprocess(self, context, prompt):
        if fmtr.is_multi_task_prompt(prompt):
            # Hold the original indent so we can restore indentation in postprocess
            original_indent = prompt.find('#')
            # WCA codegen endpoint requires prompt to end with \n
            if prompt.endswith('\n') is False:
                prompt = f"{prompt}\n"
            # Workaround for https://github.com/rh-ibm-synergy/wca-feedback/issues/3
            prompt = prompt.lstrip()
        else:
            # once we switch completely to WCA, we should be able to remove this entirely
            # since they're doing the same preprocessing on their side
            original_indent = prompt.find("name")
            context, prompt = fmtr.preprocess(context, prompt)

        return context, prompt, original_indent

    def postprocess(self, recommendation, prompt, context, user, suggestion_id, indent):
        ari_caller = apps.get_app_config("ai").get_ari_caller()
        if not ari_caller:
            logger.warn('skipped ari post processing because ari was not initialized')
        # check for commercial users for lint processing
        is_commercial = user.rh_user_has_seat
        if is_commercial:
            ansible_lint_caller = apps.get_app_config("ai").get_ansible_lint_caller()
            if not ansible_lint_caller:
                logger.warn(
                    'skipped ansible lint post processing because ansible lint was not initialized'
                )
        else:
            ansible_lint_caller = None
            logger.debug(
                'skipped ansible lint post processing as lint processing is allowed for'
                ' Commercial Users only!'
            )

        exception = None

        # We don't currently expect or support more than one prediction.
        if len(recommendation["predictions"]) != 1:
            raise Exception(
                f"unexpected predictions array length {len(recommendation['predictions'])}"
            )

        recommendation_yaml = recommendation["predictions"][0]
        recommendation_problem = None
        truncated_yaml = None
        postprocessed_yaml = None
        tasks = []
        task_names = fmtr.get_task_names_from_prompt(prompt)
        for task_name in task_names:
            tasks.append({"name": task_name})
        ari_results = None

        # check if the recommendation_yaml is a valid YAML
        try:
            _ = yaml.safe_load(recommendation_yaml)
        except Exception as exc:
            # the recommendation YAML can have a broken line at the bottom
            # because the token size of the wisdom model is limited.
            # so we try truncating the last line of the recommendation here.
            truncated, truncated_yaml = truncate_recommendation_yaml(recommendation_yaml)
            if truncated:
                try:
                    _ = yaml.safe_load(truncated_yaml)
                    logger.debug(
                        f"suggestion id: {suggestion_id}, "
                        f"truncated recommendation: \n{truncated_yaml}"
                    )
                    recommendation_yaml = truncated_yaml
                except Exception as exc:
                    recommendation_problem = exc
            else:
                recommendation_problem = exc
            if recommendation_problem:
                logger.error(
                    f'recommendation_yaml is not a valid YAML: '
                    f'\n{recommendation_yaml}'
                    f'\nException:\n{recommendation_problem}'
                )
                # if the recommentation is not a valid yaml, record it as an exception
                exception = recommendation_problem
        if ari_caller:
            start_time = time.time()
            postprocess_details = []
            try:
                # otherwise, do postprocess here
                logger.debug(
                    f"suggestion id: {suggestion_id}, "
                    f"original recommendation: \n{recommendation_yaml}"
                )
                postprocessed_yaml, ari_results = ari_caller.postprocess(
                    recommendation_yaml, prompt, context
                )
                logger.debug(
                    f"suggestion id: {suggestion_id}, "
                    f"post-processed recommendation: \n{postprocessed_yaml}"
                )
                logger.debug(
                    f"suggestion id: {suggestion_id}, "
                    f"post-process detail: {json.dumps(ari_results)}"
                )
                recommendation["predictions"][0] = postprocessed_yaml
                for ari_result in ari_results:
                    postprocess_details.append(
                        {"name": ari_result["name"], "rule_details": ari_result["rule_details"]}
                    )

            except Exception as exc:
                exception = exc
                # return the original recommendation if we failed to postprocess
                logger.exception(
                    f'failed to postprocess recommendation with prompt {prompt} '
                    f'context {context} and model recommendation {recommendation}'
                )
            finally:
                self.write_to_segment(
                    user,
                    suggestion_id,
                    recommendation_yaml,
                    truncated_yaml,
                    postprocessed_yaml,
                    postprocess_details,
                    exception,
                    start_time,
                    "ARI",
                )
                if exception:
                    raise exception

        if ansible_lint_caller:
            start_time = time.time()
            try:
                if postprocessed_yaml:
                    # Post-processing by running Ansible Lint to ARI processed yaml
                    postprocessed_yaml = ansible_lint_caller.run_linter(postprocessed_yaml)
                else:
                    # Post-processing by running Ansible Lint to model server predictions
                    postprocessed_yaml = ansible_lint_caller.run_linter(recommendation_yaml)
                # Stripping the leading STRIP_YAML_LINE that was added by above processing
                if postprocessed_yaml.startswith(STRIP_YAML_LINE):
                    postprocessed_yaml = postprocessed_yaml[len(STRIP_YAML_LINE) :]
                recommendation["predictions"][0] = postprocessed_yaml
            except Exception as exc:
                exception = exc
                # return the original recommendation if we failed to postprocess
                logger.exception(
                    f'failed to postprocess recommendation with prompt {prompt} '
                    f'context {context} and model recommendation {recommendation}'
                )
            finally:
                self.write_to_segment(
                    user,
                    suggestion_id,
                    recommendation_yaml,
                    truncated_yaml,
                    postprocessed_yaml,
                    None,
                    exception,
                    start_time,
                    "ansible-lint",
                )
                if exception:
                    raise exception

        # adjust indentation as per default ansible-lint configuration
        indented_yaml = fmtr.adjust_indentation(recommendation["predictions"][0])

        # restore original indentation
        indented_yaml = fmtr.restore_indentation(indented_yaml, indent)
        recommendation["predictions"][0] = indented_yaml
        logger.debug(f"suggestion id: {suggestion_id}, indented recommendation: \n{indented_yaml}")

        # gather data for completion segment event
        for i, task in enumerate(tasks):
            if fmtr.is_multi_task_prompt(prompt):
                task["prediction"] = fmtr.extract_task(
                    recommendation["predictions"][0], task["name"]
                )
            else:
                task["prediction"] = recommendation["predictions"][0]
            if ari_results is not None:
                ari_result = ari_results[i]
                fqcn_module = ari_result["fqcn_module"]
                if fqcn_module is not None:
                    task["module"] = fqcn_module
                    index = fqcn_module.rfind(".")
                    if index != -1:
                        task["collection"] = fqcn_module[:index]

        return recommendation, tasks

    def write_to_segment(
        self,
        user,
        suggestion_id,
        recommendation_yaml,
        truncated_yaml,
        postprocessed_yaml,
        postprocess_detail,
        exception,
        start_time,
        event_type,
    ):
        duration = round((time.time() - start_time) * 1000, 2)
        problem = (
            exception.problem
            if isinstance(exception, MarkedYAMLError)
            else str(exception)
            if str(exception)
            else exception.__class__.__name__
        )
        if event_type == "ARI":
            event = {
                "exception": exception is not None,
                "problem": problem,
                "duration": duration,
                "recommendation": recommendation_yaml,
                "truncated": truncated_yaml,
                "postprocessed": postprocessed_yaml,
                "details": postprocess_detail,
                "suggestionId": str(suggestion_id) if suggestion_id else None,
            }
            send_segment_event(event, "postprocess", user)
        if event_type == "ansible-lint":
            event = {
                "exception": exception is not None,
                "problem": problem,
                "duration": duration,
                "recommendation": recommendation_yaml,
                "postprocessed": postprocessed_yaml,
                "suggestionId": str(suggestion_id) if suggestion_id else None,
            }
            send_segment_event(event, "postprocessLint", user)


class Feedback(APIView):
    """
    Feedback API for the AI service
    """

    from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
    from rest_framework import permissions

    permission_classes = [
        permissions.IsAuthenticated,
        IsAuthenticatedOrTokenHasScope,
        AcceptedTermsPermission,
    ]
    required_scopes = ['read', 'write']

    throttle_cache_key_suffix = '_feedback'
    throttle_cache_multiplier = 6.0

    @extend_schema(
        request=FeedbackRequestSerializer,
        responses={
            200: OpenApiResponse(description='Success'),
            400: OpenApiResponse(description='Bad Request'),
            401: OpenApiResponse(description='Unauthorized'),
        },
        summary="Feedback API for the AI service",
    )
    def post(self, request) -> Response:
        exception = None
        validated_data = {}
        try:
            request_serializer = FeedbackRequestSerializer(data=request.data)
            request_serializer.is_valid(raise_exception=True)
            validated_data = request_serializer.validated_data
            logger.info(f"feedback request payload from client: {validated_data}")
            return Response({"message": "Success"}, status=rest_framework_status.HTTP_200_OK)
        except serializers.ValidationError as exc:
            exception = exc
            return Response({"message": str(exc)}, status=exc.status_code)
        except Exception as exc:
            exception = exc
            logger.exception(f"An exception {exc.__class__} occurred in sending a feedback")
            return Response(
                {"message": "Failed to send feedback"},
                status=rest_framework_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        finally:
            self.write_to_segment(request.user, validated_data, exception, request.data)

    def write_to_segment(
        self,
        user: User,
        validated_data: dict,
        exception: Exception = None,
        request_data=None,
    ) -> None:
        inline_suggestion_data: InlineSuggestionFeedback = validated_data.get("inlineSuggestion")
        ansible_content_data: AnsibleContentFeedback = validated_data.get("ansibleContent")
        suggestion_quality_data: SuggestionQualityFeedback = validated_data.get(
            "suggestionQualityFeedback"
        )
        sentiment_feedback_data: SentimentFeedback = validated_data.get("sentimentFeedback")
        issue_feedback_data: IssueFeedback = validated_data.get("issueFeedback")
        if inline_suggestion_data:
            event = {
                "latency": inline_suggestion_data.get('latency'),
                "userActionTime": inline_suggestion_data.get('userActionTime'),
                "action": inline_suggestion_data.get('action'),
                "suggestionId": str(inline_suggestion_data.get('suggestionId', '')),
                "activityId": str(inline_suggestion_data.get('activityId', '')),
                "exception": exception is not None,
            }
            send_segment_event(event, "inlineSuggestionFeedback", user)
        if ansible_content_data:
            event = {
                "content": ansible_content_data.get('content'),
                "documentUri": ansible_content_data.get('documentUri'),
                "trigger": ansible_content_data.get('trigger'),
                "activityId": str(ansible_content_data.get('activityId', '')),
                "exception": exception is not None,
            }
            send_segment_event(event, "ansibleContentFeedback", user)
        if suggestion_quality_data:
            event = {
                "prompt": suggestion_quality_data.get('prompt'),
                "providedSuggestion": suggestion_quality_data.get('providedSuggestion'),
                "expectedSuggestion": suggestion_quality_data.get('expectedSuggestion'),
                "additionalComment": suggestion_quality_data.get('additionalComment'),
                "exception": exception is not None,
            }
            send_segment_event(event, "suggestionQualityFeedback", user)
        if sentiment_feedback_data:
            event = {
                "value": sentiment_feedback_data.get('value'),
                "feedback": sentiment_feedback_data.get('feedback'),
                "exception": exception is not None,
            }
            send_segment_event(event, "sentimentFeedback", user)
        if issue_feedback_data:
            event = {
                "type": issue_feedback_data.get('type'),
                "title": issue_feedback_data.get('title'),
                "description": issue_feedback_data.get('description'),
                "exception": exception is not None,
            }
            send_segment_event(event, "issueFeedback", user)

        feedback_events = [
            inline_suggestion_data,
            ansible_content_data,
            suggestion_quality_data,
            sentiment_feedback_data,
            issue_feedback_data,
        ]
        if exception and all(not data for data in feedback_events):
            # When an exception is thrown before inline_suggestion_data or ansible_content_data
            # is set, we send request_data to Segment after having anonymized it.
            ano_request_data = anonymizer.anonymize_struct(request_data)
            if "inlineSuggestion" in request_data:
                event_type = "inlineSuggestionFeedback"
            elif "suggestionQualityFeedback" in request_data:
                event_type = "suggestionQualityFeedback"
            elif "sentimentFeedback" in request_data:
                event_type = "sentimentFeedback"
            elif "issueFeedback" in request_data:
                event_type = "issueFeedback"
            else:
                event_type = "ansibleContentFeedback"

            event = {
                "data": ano_request_data,
                "exception": str(exception),
            }
            send_segment_event(event, event_type, user)


def truncate_recommendation_yaml(recommendation_yaml: str) -> tuple[bool, str]:
    lines = recommendation_yaml.splitlines()
    lines = [line for line in lines if line.strip() != ""]

    # process the input only when it has multiple lines
    if len(lines) < 2:
        return False, recommendation_yaml

    # if the last line can be parsed as YAML successfully,
    # we do not need to try truncating.
    last_line = lines[-1]
    is_last_line_valid = False
    try:
        _ = yaml.safe_load(last_line)
        is_last_line_valid = True
    except Exception:
        pass
    if is_last_line_valid:
        return False, recommendation_yaml

    truncated_yaml = "\n".join(lines[:-1])
    return True, truncated_yaml


class Attributions(GenericAPIView):
    """
    Returns attributions that were the highest likelihood sources for a given code suggestion.
    """

    serializer_class = AttributionRequestSerializer

    from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
    from rest_framework import permissions

    permission_classes = [
        permissions.IsAuthenticated,
        IsAuthenticatedOrTokenHasScope,
        AcceptedTermsPermission,
    ]
    required_scopes = ['read', 'write']

    throttle_cache_key_suffix = '_attributions'

    @extend_schema(
        request=AttributionRequestSerializer,
        responses={
            200: AttributionResponseSerializer,
            400: OpenApiResponse(description='Bad Request'),
            401: OpenApiResponse(description='Unauthorized'),
            429: OpenApiResponse(description='Request was throttled'),
            503: OpenApiResponse(description='Service Unavailable'),
        },
        summary="Code suggestion attributions",
    )
    def post(self, request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        suggestion_id = str(serializer.validated_data.get('suggestionId', ''))
        start_time = time.time()
        try:
            encode_duration, search_duration, resp_serializer = self.perform_search(
                serializer, request.user
            )
        except Exception as exc:
            logger.error(f"Failed to search for attributions\nException:\n{exc}")
            return Response({'message': "Unable to complete the request"}, status=503)
        duration = round((time.time() - start_time) * 1000, 2)
        attribution_encoding_hist.observe(encode_duration / 1000)
        attribution_search_hist.observe(search_duration / 1000)
        # Currently the only thing from Attributions that is going to Segment is the
        # inferred sources, which do not seem to need anonymizing.
        self.write_to_segment(
            request.user,
            suggestion_id,
            duration,
            encode_duration,
            search_duration,
            resp_serializer.validated_data,
        )

        return Response(resp_serializer.data, status=rest_framework_status.HTTP_200_OK)

    def perform_search(self, serializer, user: User):
        index = None
        if settings.LAUNCHDARKLY_SDK_KEY:
            model_tuple = feature_flags.get("model_name", user, "")
            logger.debug(f"flag model_name has value {model_tuple}")
            model_parts = model_tuple.split(':')
            if len(model_parts) == 4:
                *_, index = model_parts
                logger.info(f"using index '{index}' for content matching")

        data = ai_search.search(serializer.validated_data['suggestion'], index)
        resp_serializer = AttributionResponseSerializer(data={'attributions': data['attributions']})
        if not resp_serializer.is_valid():
            logging.error(resp_serializer.errors)
        return data['meta']['encode_duration'], data['meta']['search_duration'], resp_serializer

    def write_to_segment(
        self, user, suggestion_id, duration, encode_duration, search_duration, attribution_data
    ):
        attributions = attribution_data.get('attributions', [])
        event = {
            'suggestionId': suggestion_id,
            'duration': duration,
            'encode_duration': encode_duration,
            'search_duration': search_duration,
            'attributions': attributions,
        }
        send_segment_event(event, "attribution", user)
