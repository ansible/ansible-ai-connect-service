import logging
from typing import Tuple

from ..data.data_model import Payload

logger = logging.getLogger(__name__)


def openai_to_wisdom(payload: Payload) -> Tuple[Payload, str]:
    # remove extra newlines from end of context
    context_lines = payload.prompt.strip('\n').split("\n")
    context_last_line = context_lines[-1].strip()
    logger.debug(f"Extracting prompt from line: {context_last_line}")

    if context_last_line.startswith("- name:"):
        prompt_type = "task-name"
        payload.prompt = context_last_line
    elif context_last_line.startswith("#"):
        # Extract prompt from comment and add "- name:"
        prompt_type = "comment"
        payload.prompt = "- name: " + context_last_line.split("#")[-1].strip()
    elif context_last_line:
        # TODO: Currently Generic is disabled client-side
        # Extract prompt from generic and add "- name:"
        prompt_type = "generic"
        payload.prompt = "- name: " + context_last_line
    else:
        prompt_type = "empty"
        payload.prompt = ""

    # remove prompt line from context
    payload.context = "\n".join(context_lines[:-1])

    logger.debug(f"Identified line type: {prompt_type}")
    logger.debug(f"Extracted prompt: {payload.prompt}")
    return (payload, prompt_type)
