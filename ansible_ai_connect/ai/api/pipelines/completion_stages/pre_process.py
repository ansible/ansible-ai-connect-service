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

from django.conf import settings
from django_prometheus.conf import NAMESPACE
from prometheus_client import Histogram

from ansible_ai_connect.ai.api import formatter as fmtr
from ansible_ai_connect.ai.api.exceptions import (
    PreprocessInvalidYamlException,
    process_error_count,
)
from ansible_ai_connect.ai.api.pipelines.common import PipelineElement
from ansible_ai_connect.ai.api.pipelines.completion_context import CompletionContext

logger = logging.getLogger(__name__)

preprocess_hist = Histogram(
    "preprocessing_latency_seconds",
    "Histogram of pre-processing time",
    namespace=NAMESPACE,
)


def completion_pre_process(context: CompletionContext):
    prompt = context.payload.prompt
    original_prompt, _ = fmtr.extract_prompt_and_context(context.payload.original_prompt)
    payload_context = context.payload.context

    # Additional context (variables) is supported when
    #
    #   1. ENABLE_ADDITIONAL_CONTEXT setting is set to True, and
    #   2. The user has a seat (=she/he is a commercial user).
    #
    user = context.request.user
    is_commercial = user.rh_user_has_seat
    if settings.ENABLE_ADDITIONAL_CONTEXT and is_commercial:
        additionalContext = context.metadata.get("additionalContext", {})
    else:
        additionalContext = {}

    multi_task = fmtr.is_multi_task_prompt(prompt)
    context.original_indent = prompt.find("#" if multi_task else "name")

    # fmtr.preprocess() performs:
    #
    #   1. Insert additional context (variables), and
    #   2. Formatting/normalizing prompt/context YAML data,
    #
    # Calling fmtr.preprocess for of (2) is redundant in WCA case
    # because WCA is already doing this. However, enhanced context
    # support also relies on this preprocess step, so we will
    # always call fmtr.preprocess, regardless of model server.
    #
    ansibleFileType = context.metadata.get("ansibleFileType", "playbook")
    context.payload.context, context.payload.prompt = fmtr.preprocess(
        payload_context, prompt, ansibleFileType, additionalContext
    )
    if not multi_task:
        # We are currently more forgiving on leading spacing of single task
        # prompts than multi task prompts. In order to use the "original"
        # single task prompt successfull in post-processing, we need to
        # ensure its spacing aligns with the normalized context we got
        # back from preprocess. We can calculate the proper spacing from the
        # normalized prompt.
        normalized_indent = len(context.payload.prompt) - len(context.payload.prompt.lstrip())
        normalized_original_prompt = fmtr.normalize_yaml(original_prompt)
        original_prompt = " " * normalized_indent + normalized_original_prompt
    context.payload.original_prompt = original_prompt


class PreProcessStage(PipelineElement):
    def process(self, context: CompletionContext) -> None:
        start_time = time.time()
        payload = context.payload
        try:
            completion_pre_process(context)
        except Exception as exc:
            process_error_count.labels(stage="pre-processing").inc()
            # return the original prompt, context
            logger.error(
                f"failed to preprocess:\n{payload.context}{payload.prompt}\nException:\n{exc}"
            )
            raise PreprocessInvalidYamlException()

        finally:
            duration = round((time.time() - start_time) * 1000, 2)
            preprocess_hist.observe(duration / 1000)  # millisec to seconds
