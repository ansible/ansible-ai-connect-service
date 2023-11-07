import logging
import time

from ai.api import formatter as fmtr
from ai.api.pipelines.common import PipelineElement, process_error_count
from ai.api.pipelines.completion_context import CompletionContext
from django.conf import settings
from django_prometheus.conf import NAMESPACE
from prometheus_client import Histogram
from rest_framework.response import Response

logger = logging.getLogger(__name__)

preprocess_hist = Histogram(
    'preprocessing_latency_seconds',
    "Histogram of pre-processing time",
    namespace=NAMESPACE,
)


def completion_pre_process(context: CompletionContext):
    cp = context.payload.prompt
    cc = context.payload.context

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

    multi_task = fmtr.is_multi_task_prompt(cp)
    context.original_indent = cp.find('#' if multi_task else "name")

    # fmtr.preprocess() performs:
    #
    #   1. Insert additional context (variables), and
    #   2. Formatting prompt/context YAML data,
    #
    # When non-empty additional context is given, fmtr.preprocess() needs to
    # be called. Otherwise, it is called when a non-multi task prompt is
    # specified because multi-task prompts are supported by WCA only and WCA
    # contains its own formatter for 2.
    #
    if additionalContext or not multi_task:
        ansibleFileType = context.metadata.get("ansibleFileType", "playbook")
        context.payload.context, context.payload.prompt = fmtr.preprocess(
            cc, cp, ansibleFileType, additionalContext
        )


class PreProcessStage(PipelineElement):
    def process(self, context: CompletionContext) -> None:
        start_time = time.time()
        payload = context.payload
        try:
            completion_pre_process(context)
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
            context.response = Response({'message': message}, status=400)

        finally:
            duration = round((time.time() - start_time) * 1000, 2)
            preprocess_hist.observe(duration / 1000)  # millisec to seconds
