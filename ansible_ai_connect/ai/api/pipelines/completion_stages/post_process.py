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

import yaml
from django.apps import apps
from django_prometheus.conf import NAMESPACE
from prometheus_client import Histogram
from yaml.error import MarkedYAMLError

import ansible_ai_connect.ai.api.telemetry.schema1 as schema1
from ansible_ai_connect.ai.api import formatter as fmtr
from ansible_ai_connect.ai.api.exceptions import (
    PostprocessException,
    process_error_count,
)
from ansible_ai_connect.ai.api.pipelines.common import PipelineElement
from ansible_ai_connect.ai.api.pipelines.completion_context import CompletionContext
from ansible_ai_connect.ai.api.utils.segment import send_schema1_event

logger = logging.getLogger(__name__)

STRIP_YAML_LINE = "---\n"

postprocess_hist = Histogram(
    "postprocessing_latency_seconds",
    "Histogram of post-processing time",
    namespace=NAMESPACE,
)


def get_ansible_lint_caller(user):
    """check for commercial users for lint processing"""
    is_commercial = user.rh_user_has_seat
    if is_commercial:
        ansible_lint_caller = apps.get_app_config("ai").get_ansible_lint_caller()
        if not ansible_lint_caller:
            logger.warn(
                "skipped ansible lint post processing because ansible lint was not initialized"
            )
    else:
        ansible_lint_caller = None
        logger.debug(
            "skipped ansible lint post processing as lint processing is allowed for"
            " Commercial Users only!"
        )
    return ansible_lint_caller


def write_to_segment(
    user,
    suggestion_id,
    recommendation_yaml,
    truncated_yaml,
    postprocessed_yaml,
    postprocess_detail,
    exception,
    start_time,
    event_type,
    model_id,
):
    duration = round((time.time() - start_time) * 1000, 2)
    problem = (
        exception.problem
        if isinstance(exception, MarkedYAMLError)
        else str(exception) if str(exception) else exception.__class__.__name__
    )

    if event_type == "ARI":
        schema1_event = schema1.Postprocess()
        schema1_event.details = postprocess_detail
        schema1_event.truncated = truncated_yaml

    elif event_type == "ansible-lint":

        schema1_event = schema1.PostprocessLint()
        schema1_event.postprocessed = postprocessed_yaml

    schema1_event.set_user(user)
    schema1_event.set_exception(exception)
    schema1_event.duration = duration
    schema1_event.postprocessed = postprocessed_yaml
    schema1_event.problem = problem
    schema1_event.recommendation = recommendation_yaml
    schema1_event.suggestionId = str(suggestion_id) if suggestion_id else ""

    if model_id:
        schema1_event.modelName = model_id
    send_schema1_event(schema1_event)


def trim_whitespace_lines(input: str):
    return "\n".join(line if line.strip() else "" for line in input.split("\n"))


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


def completion_post_process(context: CompletionContext):
    user = context.request.user
    model_id = context.model_id
    suggestion_id = context.payload.suggestionId
    prompt = context.payload.prompt
    payload_context = context.payload.context
    original_indent = context.original_indent
    post_processed_predictions = context.anonymized_predictions.copy()
    is_multi_task_prompt = fmtr.is_multi_task_prompt(prompt)

    ari_caller = apps.get_app_config("ai").get_ari_caller()
    if not ari_caller:
        logger.warning("skipped ari post processing because ari was not initialized")

    ansible_lint_caller = get_ansible_lint_caller(user)

    exception = None

    # We don't currently expect or support more than one prediction.
    if len(post_processed_predictions["predictions"]) != 1:
        raise PostprocessException(
            f"unexpected predictions array length {len(post_processed_predictions['predictions'])}"
        )

    recommendation_yaml = post_processed_predictions["predictions"][0]

    if not recommendation_yaml:
        raise PostprocessException(f"unexpected prediction content {recommendation_yaml}")

    recommendation_problem = None
    truncated_yaml = None
    postprocessed_yaml = None
    tasks = [{"name": task_name} for task_name in fmtr.get_task_names_from_prompt(prompt)]
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
                f"recommendation_yaml is not a valid YAML: "
                f"\n{recommendation_yaml}"
                f"\nException:\n{recommendation_problem}"
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
                recommendation_yaml, prompt, payload_context
            )
            logger.debug(
                f"suggestion id: {suggestion_id}, "
                f"post-processed recommendation: \n{postprocessed_yaml}"
            )

            post_processed_predictions["predictions"][0] = postprocessed_yaml
            tasks_with_applied_changes = []
            for index, ari_result in enumerate(ari_results):
                # Use the anonymized task name in the postprocess segment event
                postprocess_details.append(
                    {"name": tasks[index]["name"], "rule_details": ari_result["rule_details"]}
                )
                rules_with_applied_changes = [
                    k for k, v in ari_result["rule_details"].items() if v["applied_changes"]
                ]
                if rules_with_applied_changes:
                    tasks_with_applied_changes.append(
                        {"name": tasks[index]["name"], "rules": rules_with_applied_changes}
                    )

            if user.rh_user_has_seat:
                # Test for changes to the recommendation and if so log as warn.
                # WCA is already running ARI so we expect no changes.
                # Ignore any whitespace and single vs double quote changes.
                pp = (
                    postprocessed_yaml.replace(" ", "")
                    .replace("\n", "")
                    .replace('"', "")
                    .replace("'", "")
                )
                orig = (
                    recommendation_yaml.replace(" ", "")
                    .replace("\n", "")
                    .replace('"', "")
                    .replace("'", "")
                )

                if tasks_with_applied_changes or (pp != orig):
                    ari_changes_logger = logging.getLogger("ari_changes")
                    ari_changes_logger.info(
                        f"ARI CHANGES DETECTED. suggestion_id: [{suggestion_id}] "
                        f"rules_with_applied_changes: {tasks_with_applied_changes} "
                        f"recommendation_yaml: [{repr(recommendation_yaml)}] "
                        f"postprocessed_yaml: [{repr(postprocessed_yaml)}] "
                        f"prompt: [{repr(prompt)}] "
                        f"payload_context: [{repr(payload_context)}] "
                        f"postprocess_details: [{json.dumps(postprocess_details)}] "
                    )

            logger.debug(
                f"suggestion id: {suggestion_id}, "
                f"post-process detail: {json.dumps(postprocess_details)}"
            )
        except Exception as exc:
            exception = exc
            # return the original recommendation if we failed to postprocess
            logger.exception(
                f"failed to postprocess recommendation with prompt {prompt} "
                f"context {payload_context} and model recommendation {post_processed_predictions}"
            )
        finally:
            write_to_segment(
                user,
                suggestion_id,
                recommendation_yaml,
                truncated_yaml,
                postprocessed_yaml,
                postprocess_details,
                exception,
                start_time,
                "ARI",
                model_id,
            )
            if exception:
                raise exception

    if ansible_lint_caller:
        start_time = time.time()
        try:
            # Ansible Lint the ARI processed yaml else the model prediction
            input_yaml = postprocessed_yaml if postprocessed_yaml else recommendation_yaml
            # Single task predictions are missing the `- name: ` line and fail linter schema check
            if not is_multi_task_prompt:
                prompt += "\n"
                input_yaml = f"{prompt.lstrip() if ari_caller else prompt}{input_yaml}"
            postprocessed_yaml = ansible_lint_caller.run_linter(input_yaml)
            # Stripping the leading STRIP_YAML_LINE that was added by above processing
            if postprocessed_yaml.startswith(STRIP_YAML_LINE):
                postprocessed_yaml = postprocessed_yaml[len(STRIP_YAML_LINE) :]
            # Strip the task name line if single task
            if not is_multi_task_prompt and postprocessed_yaml.lstrip().startswith("- name:"):
                postprocessed_yaml = "\n".join(postprocessed_yaml.split("\n")[1:])
            post_processed_predictions["predictions"][0] = postprocessed_yaml
        except Exception as exc:
            exception = exc
            # return the original recommendation if we failed to postprocess
            logger.exception(
                f"failed to postprocess recommendation with prompt {prompt} "
                f"context {payload_context} and model recommendation {post_processed_predictions}"
            )
        finally:
            anonymized_input_yaml = (
                postprocessed_yaml if postprocessed_yaml else recommendation_yaml
            )
            write_to_segment(
                user,
                suggestion_id,
                anonymized_input_yaml,
                truncated_yaml,
                postprocessed_yaml,
                None,
                exception,
                start_time,
                "ansible-lint",
                model_id,
            )
            if exception:
                raise exception

    # If ARI is not enabled, and suggestion is multi-task, add newlines between tasks
    if not ari_caller and is_multi_task_prompt:
        post_processed_predictions["predictions"][0] = fmtr.normalize_yaml(
            post_processed_predictions["predictions"][0]
        )

    # adjust indentation as per default ansible-lint configuration
    indented_yaml = fmtr.adjust_indentation(post_processed_predictions["predictions"][0])

    # restore original indentation
    indented_yaml = fmtr.restore_indentation(indented_yaml, original_indent)

    # blank any lines containing only whitespace
    indented_yaml = trim_whitespace_lines(indented_yaml)

    # add a newline to the end if there isn't one
    if indented_yaml.endswith("\n") is False:
        indented_yaml = f"{indented_yaml}\n"

    post_processed_predictions["predictions"][0] = indented_yaml
    logger.debug(f"suggestion id: {suggestion_id}, indented recommendation: \n{indented_yaml}")

    # gather data for completion segment event
    # WARNING: the block below do inplace transformation of 'tasks', we should refact the
    # code to avoid that.
    for i, task in enumerate(tasks):
        if fmtr.is_multi_task_prompt(prompt):
            task["prediction"] = fmtr.extract_task(
                post_processed_predictions["predictions"][0], task["name"]
            )
        else:
            task["prediction"] = post_processed_predictions["predictions"][0]

        fqcn_module = None
        if ari_results is not None:
            ari_result = ari_results[i]
            fqcn_module = ari_result["fqcn_module"]
        populate_module_and_collection(fqcn_module, task)

    context.task_results = tasks
    context.post_processed_predictions = post_processed_predictions


def populate_module_and_collection(fqcn_module, task):
    if fqcn_module is None or fqcn_module == "":
        # In case the module is not part of the collections, ARI does not handle it.
        # This way, parsing the module from the prediction instead.
        fqcn_module = fmtr.get_fqcn_or_module_from_prediction(task["prediction"])

    if fqcn_module is not None:
        task["module"] = fqcn_module
        index = fqcn_module.rfind(".")
        if index != -1:
            task["collection"] = fqcn_module[:index]


class PostProcessStage(PipelineElement):
    def process(self, context: CompletionContext) -> None:
        start_time = time.time()
        payload = context.payload
        predictions = context.predictions
        try:
            completion_post_process(context)
        except Exception:
            process_error_count.labels(stage="post-processing").inc()
            logger.exception(
                f"error postprocessing prediction for suggestion {payload.suggestionId}"
            )
            # Raise a PostprocessException with setting predictions, not the exception
            # to the cause parameter. It is because the cause parameter is used for getting
            # model ID, and we cannot except exceptions from postprocess() will contain
            # the information about model ID.
            raise PostprocessException(cause=predictions)
        finally:
            duration = round((time.time() - start_time) * 1000, 2)
            postprocess_hist.observe(duration / 1000)  # millisec to seconds

        logger.debug(
            f"response from postprocess for "
            f"suggestion id {payload.suggestionId}:\n{context.anonymized_predictions}"
        )
