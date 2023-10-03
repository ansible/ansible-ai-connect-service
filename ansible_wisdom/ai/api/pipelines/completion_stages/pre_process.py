import logging
import time

from ai.api import formatter as fmtr
from ai.api.pipelines.common import PipelineElement, process_error_count
from ai.api.pipelines.completion_context import CompletionContext
from django_prometheus.conf import NAMESPACE
from prometheus_client import Histogram
from rest_framework.response import Response

logger = logging.getLogger(__name__)

preprocess_hist = Histogram(
    'preprocessing_latency_seconds',
    "Histogram of pre-processing time",
    namespace=NAMESPACE,
)


def completion_pre_process(completion_context: CompletionContext):
    cp = completion_context.payload.prompt
    cc = completion_context.payload.context
    if fmtr.is_multi_task_prompt(cp):
        # Hold the original indent so that we can restore indentation in postprocess
        original_indent = cp.find('#')
    else:
        # once we switch completely to WCA, we should be able to remove this entirely
        # since they're doing the same preprocessing on their side
        original_indent = cp.find("name")
        cc, cp = fmtr.preprocess(cc, cp)

    completion_context.payload.prompt = cp
    completion_context.payload.context = cc
    completion_context.original_indent = original_indent


class PreProcessStage(PipelineElement):
    def process(self, completion_context: CompletionContext) -> None:
        start_time = time.time()
        payload = completion_context.payload
        try:
            completion_pre_process(completion_context)
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
            completion_context.response = Response({'message': message}, status=400)

        finally:
            duration = round((time.time() - start_time) * 1000, 2)
            preprocess_hist.observe(duration / 1000)  # millisec to seconds
