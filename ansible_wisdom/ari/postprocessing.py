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

import contextlib
import json
import logging
import timeit

import yaml
from ansible_risk_insight.scanner import ARIScanner
from django.conf import settings

from ansible_wisdom.ai.api import formatter as fmtr

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
            first_line_lstrip = first_line.lstrip()
            extra_indent = 0
            if first_line_lstrip.startswith('- ') is False:
                # single-line suggestions indent two extra spaces
                extra_indent = 2
            suggestion_indent = len(first_line) - len(first_line_lstrip)
            if suggestion_indent < prompt_indent + extra_indent:
                padding_level = (prompt_indent + extra_indent) - suggestion_indent
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
        # **# sample prompt          <-- multi task prompt_indent
        # **- name: sample propmt    <-- suggestion_indent should equal prompt_indent
        # ****ansible.builtin.debug:
        #       msg: "test"

        prompt_indent = cls.get_indent_size(prompt)
        is_playbook = False
        if context:
            try:
                context_data = yaml.safe_load(context)
                if isinstance(context_data, list) and any(
                    play_keyword in context_data[-1]
                    for play_keyword in ["tasks", "pre_tasks", "post_tasks", "handlers"]
                ):
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

        logger.debug(f"generated playbook yaml: \n{playbook_yaml}")
        return playbook_yaml, is_playbook

    def postprocess(self, inference_output, prompt, context):
        input_yaml, is_playbook = self.make_input_yaml(context, prompt, inference_output)

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

        ari_results = []
        modified_yamls = []

        original_task_names = fmtr.get_task_names_from_prompt(prompt)
        # For multi-task, we also need to also retrieve the task names from the
        # inference output, because we've run this through the anonymizer again
        # and PII values may havechanged. We need to use this value to retrieve
        # the correct task from ARI.
        predicted_task_names = original_task_names
        if fmtr.is_multi_task_prompt(prompt):
            predicted_task_names = fmtr.get_task_names_from_tasks(inference_output)
        for i, original_anonymized_task_name in enumerate(original_task_names):
            predicted_task_name = predicted_task_names[i]
            detail_data = {}
            ari_result = {"name": original_anonymized_task_name, "rule_details": detail_data}
            ari_results.append(ari_result)
            task = target.task(name=predicted_task_name)
            if task:
                rule_result = task.find_result(rule_id=settings.ARI_RULE_FOR_OUTPUT_RESULT)
                detail = rule_result.get_detail()
                aggregated_detail = detail.get("detail", {})

                if fmtr.is_multi_task_prompt(prompt):
                    # Here we are using the anonyimized prompt, NOT what came back
                    # from WCA, which should be the same.
                    # TODO: See if we can get this task name back from ARI instead,
                    # which might result in e.g. values being replaced with variables
                    modified_yamls.append(f"- name: {predicted_task_name}")

                task_modified_yaml = detail.get("modified_yaml")
                if task_modified_yaml is None:
                    raise Exception("no modified yaml returned from ARI")
                modified_yamls.append(task_modified_yaml)

                mutation_result = aggregated_detail.get("mutation_result", {})
                ari_result["fqcn_module"] = aggregated_detail.get("correct_fqcn", "")
                for rule_id in mutation_result:
                    rule_detail = mutation_result[rule_id]
                    if not rule_detail:
                        continue
                    _result = task.find_result(rule_id=rule_id)
                    if _result:
                        if "description" not in rule_detail:
                            rule_detail["description"] = _result.description
                        if _result.rule:
                            rule_detail["version"] = _result.rule.version
                            rule_detail["commit_id"] = _result.rule.commit_id
                        rule_detail["duration"] = _result.duration
                        rule_detail["matched"] = _result.matched
                        rule_detail["error"] = _result.error
                    detail_data[rule_id] = rule_detail
            else:
                raise Exception('task not found in ARI postprocess results')

        modified_yaml = '\n'.join(modified_yamls)
        # return inference_output
        logger.debug("--before--")
        logger.debug(inference_output)
        logger.debug("--after--")
        logger.debug(modified_yaml)
        logger.debug("--details--")
        logger.debug(json.dumps(ari_results, indent=2))

        return modified_yaml, ari_results
