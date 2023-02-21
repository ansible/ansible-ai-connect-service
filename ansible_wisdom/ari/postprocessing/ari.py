import contextlib
import json
import logging
import os
import timeit

import yaml
from ansible_risk_insight.scanner import ARIScanner, Config

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


def is_enabled():
    rules_dir = os.path.join(os.getenv('KB_REMOTE_ARI_PATH', '/etc/ari/kb/'), 'rules')
    return os.path.exists(rules_dir)


def default_config():
    return Config(
        rules_dir=os.path.join(os.getenv('KB_REMOTE_ARI_PATH', '/etc/ari/kb/'), 'rules'),
        data_dir=os.path.join(os.getenv('KB_REMOTE_ARI_PATH', '/etc/ari/kb/'), 'data'),
        rules=[
            "P001",
            "P002",
            "P003",
            "P004",
            "W001",
            "W003",
            "W004",
            "W005",
            "W006",
            "W007",
            "W008",
            "W009",
            "W010",
            "W012",
            "W013",
        ],
    )


class ARICaller:
    def __init__(self, config, silent) -> None:
        self.ari_scanner = ARIScanner(config=config, silent=silent)

    @classmethod
    def indent(cls, text, level):
        lines = [" " * level + line for line in text.splitlines()]
        return "\n".join(lines)

    @classmethod
    def make_playbook_yaml(cls, context, prompt, inference_output):
        inference_output_is_playbook = False

        # if prompt is at play level, the inference output will be a play instead of a task
        # when the output contains `hosts:` and `tasks:`, it is a play
        if "hosts:" in inference_output and "tasks:" in inference_output:
            inference_output_is_playbook = True

        if inference_output_is_playbook:
            playbook_yaml = prompt + "\n"
            playbook_yaml += inference_output
            play_data = yaml.safe_load(inference_output)
            tasks = play_data.get("tasks", [])
            task_name = ""
            if tasks:
                task_name = tasks[-1].get("name", "")
            return playbook_yaml, task_name

        # if there is no contexts, use the dummy playbook as a context
        #  since ARI assumes that an input is a playbook
        dummy_playbook = '''- name: playbook
  hosts: localhost
  connection: local
  tasks:
'''

        if not context:
            context = dummy_playbook

        lines = context.splitlines()
        task_indent_level = 0
        inside_tasks = False
        insert_index = -1
        for j, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("tasks:"):
                inside_tasks = True
                if j == len(lines) - 1:
                    task_indent_level = len(line.split("tasks:")[0]) + 2
                else:
                    task_indent_level = len(lines[j + 1].split("-")[0])
            if inside_tasks:
                if j == len(lines) - 1:
                    insert_index = len(lines)
                else:
                    next_line_indent_level = len(lines[j + 1]) - len(lines[j + 1].lstrip())
                    if next_line_indent_level < task_indent_level:
                        insert_index = j + 1
                if insert_index >= 0:
                    inside_tasks = False
                    break
        if insert_index == -1:
            raise ValueError("Failed to find the place where the task should be inserted")

        lines.insert(insert_index, cls.indent(prompt, task_indent_level))
        lines.insert(insert_index + 1, cls.indent(inference_output, task_indent_level))
        playbook_yaml = "\n".join(lines)
        task_name = prompt.split("name:")[-1].strip()
        return playbook_yaml, task_name

    def postprocess(self, inference_output, prompt, context):
        sprompt = prompt.lstrip()
        playbook_yaml, task_name = self.make_playbook_yaml(context, sprompt, inference_output)

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
        if task:
            rule_result = task.find_result(rule_id="W007")
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
