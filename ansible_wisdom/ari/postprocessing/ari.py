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
    def get_indent_size(cls, prompt):
        prompt_indent = 0
        if prompt:
            prompt_indent = len(prompt) - len(prompt.lstrip())
        return prompt_indent

    @classmethod
    def indent_suggestion(cls, suggestion, prompt_indent):
        if suggestion:
            lines = suggestion.splitlines()
            first_line = lines[0]
            suggestion_indent = len(first_line) - len(first_line.lstrip())
            if suggestion_indent < prompt_indent + 2:
                padding_level = (prompt_indent + 2) - suggestion_indent
                suggestion = cls.indent(suggestion, padding_level)
        return suggestion

    @classmethod
    def make_input_yaml(cls, context, prompt, inference_output):
        # align prompt and suggestion to make a valid playbook yaml
        #
        # e.g.)
        #
        # - hosts: all
        #   tasks:
        # **- name: sample propmt   <-- prompt_indent could be 0 for roles or any number
        #                               of spaces for playbook
        # ****ansible.builtin.debug:   <-- suggestion_indent should be prompt_indent + 2
        #       msg: "test"

        prompt_indent = cls.get_indent_size(prompt)
        is_playbook = False
        if context:
            try:
                context_dict = yaml.safe_load(context)
                if "tasks" in context_dict:
                    is_playbook = True
            except Exception:
                logger.exception('the received context could not be loaded as a YAML')
        suggestion = cls.indent_suggestion(inference_output, prompt_indent)
        playbook_yaml = context + "\n" + prompt + "\n" + suggestion
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
        logger.debug(f"generated playbook yaml: \n{playbook_yaml}")
        return playbook_yaml, is_playbook, task_name

    def postprocess(self, inference_output, prompt, context):
        input_yaml, is_playbook, task_name = self.make_input_yaml(context, prompt, inference_output)

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

        target_type = "playbook"
        if not is_playbook:
            target_type = "taskfile"

        result = self.ari_scanner.evaluate(
            type=target_type,
            raw_yaml=input_yaml,
        )
        target = result.find_target(yaml_str=input_yaml, target_type=target_type)
        if not target:
            raise ValueError(f"the {target_type} was not found")

        task = target.task(name=task_name)
        modified_yaml = inference_output
        detail_data = {}
        if task:
            rule_result = task.find_result(rule_id=settings.ARI_RULE_FOR_OUTPUT_RESULT)
            detail = rule_result.get_detail()
            detail_data = detail.get("detail", "")
            prompt_indent = self.get_indent_size(prompt)
            modified_yaml = self.indent_suggestion(detail.get("modified_yaml", ""), prompt_indent)

        # return inference_output
        logger.debug("--before--")
        logger.debug(inference_output)
        logger.debug("--after--")
        logger.debug(modified_yaml)
        logger.debug("--detail--")
        logger.debug(json.dumps(detail_data, indent=2))

        return modified_yaml
