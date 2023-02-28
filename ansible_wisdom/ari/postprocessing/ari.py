import contextlib
import json
import logging
import timeit

import yaml
from ansible_risk_insight.scanner import ARIScanner
from django.conf import settings

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def time_activity(activity_name: str):
    """Context Manager to report duration of an activity"""
    logger.info(f'[Timing] {activity_name} start.')
    start = timeit.default_timer()
    try:
        yield
    finally:
        duration = timeit.default_timer() - start
        logger.info(f'[Timing] {activity_name} finished (Took {duration:.2f}s)')


class ARICaller:
    def __init__(self, config, silent) -> None:
        self.ari_scanner = ARIScanner(config=config, silent=silent)

    @classmethod
    def indent(cls, text, level):
        lines = [" " * level + line for line in text.splitlines()]
        return "\n".join(lines)

    @classmethod
    def make_playbook_yaml(cls, context, prompt, inference_output):
        # align prompt and suggestion to make a valid playbook yaml
        #
        # e.g.)
        #
        # - hosts: all
        #   tasks:
        # **- name: sample propmt   <-- prompt_indent should be 2 (or 4 is ok too)
        # ****ansible.builtin.debug:   <-- suggestion_indent should be prompt_indent + 2
        #       msg: "test"

        m_prompt = prompt
        prompt_indent = 0
        if m_prompt:
            prompt_indent = len(m_prompt) - len(m_prompt.lstrip())
            if prompt_indent == 0:
                m_prompt = cls.indent(m_prompt, 2)
                prompt_indent = 2
        suggestion = inference_output
        if suggestion:
            lines = suggestion.splitlines()
            first_line = lines[0]
            suggestion_indent = len(first_line) - len(first_line.lstrip())
            if suggestion_indent < prompt_indent + 2:
                padding_level = (prompt_indent + 2) - suggestion_indent
                suggestion = cls.indent(suggestion, padding_level)
        playbook_yaml = context + "\n" + m_prompt + "\n" + suggestion
        try:
            # check if the playbook yaml is valid
            _ = yaml.safe_load(playbook_yaml)
        except Exception:
            logger.exception(
                f'failed to create a valid playbook YAML which can be loaded correctly: '
                f'the created one is the following:\n{playbook_yaml}'
            )
            raise
        task_name = prompt.split("name:")[-1].strip()
        return playbook_yaml, task_name

    def postprocess(self, inference_output, prompt, context):
        playbook_yaml, task_name = self.make_playbook_yaml(context, prompt, inference_output)

        # print("---context---")
        # print(context)
        # print("---prompt---")
        # print(prompt)
        # print("---inference_output---")
        # print(inference_output)
        # print("---playbook_yaml---")
        # print(playbook_yaml)
        # print("---task_name---")
        # print(task_name)

        result = self.ari_scanner.evaluate(
            type="playbook",
            playbook_yaml=playbook_yaml,
        )
        playbook = result.playbook(yaml_str=playbook_yaml)
        if not playbook:
            raise ValueError("the playbook was not found")

        task = playbook.task(name=task_name)
        modified_yaml = inference_output
        detail_data = {}
        if task:
            rule_result = task.find_result(rule_id=settings.ARI_RULE_FOR_OUTPUT_RESULT)
            detail = rule_result.get_detail()
            detail_data = detail.get("detail", "")
            modified_yaml = detail.get("modified_yaml", "")

        # return inference_output
        logger.debug("--before--")
        logger.debug(inference_output)
        logger.debug("--after--")
        logger.debug(modified_yaml)
        logger.debug("--detail--")
        logger.debug(json.dumps(detail_data, indent=2))

        return modified_yaml
