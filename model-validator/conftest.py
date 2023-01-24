#!/usr/bin/env python3

from pathlib import Path
from requests.models import Response
from typing import Any, List, Optional
import json
import logging
import pytest
import requests
import yaml

model_mesh_host = "http://localhost:7080"


task_dict_t = dict[str, Any]


logging.basicConfig(filename='model-validator.log', level=logging.INFO)


class Task:
    known_fields = set(
        [
            "args",
            "become",
            "become_user",
            "delegate_to",
            "ignore_errors",
            "local_action",
            "loop",
            "loop_control",
            "name",
            "register",
            "with_items",
        ]
    )

    def __init__(self, struct: dict[str, Any]):
        self._struct = struct
        self.module = self.resolve_module_name()
        self.args = self.get_args()
        assert "ignore_errors" not in self._struct, "Task should not use ignore_errors"

    def get_args(self):
        if isinstance(self._struct.get("args"), dict):
            return self._struct.get("args")
        elif isinstance(self._struct[self.module], dict):
            return self._struct[self.module]
        return {}

    def resolve_module_name(self) -> str:
        keys = set(self._struct.keys())
        candidates = list(keys - Task.known_fields)
        assert (
            len(candidates) != 0
        ), f"Cannot find a module name in the task suggestion, task={self._struct}"
        assert (
            len(candidates) < 2
        ), f"Too many potential module names in the task suggestion, candidates={candidates}"
        return candidates[0]

    def yaml_print(self):
        print(yaml.dump(self._struct))

    def use_loop(self) -> str:
        for i in [
            "loop",
            "loop_control",
            "with_cartesian",
            "with_dict",
            "with_flattened",
            "with_indexed_items",
            "with_items",
            "with_list",
            "with_nested",
            "with_random_choice",
            "with_sequence",
            "with_subelements",
            "with_together",
        ]:
            if i in self._struct:
                return i

    def use_privilege_escalation(self) -> bool:
        return "become" in self._struct

    def assert_has_no_loop(self):
        """Raise an error if the task uses a looping system"""
        assert not self.use_loop(), f"The task should not use a loop"


def unwrap_prediction(r: Response) -> dict[str, Any]:
    logging.debug('ANSWER: %s', {r.text})
    json_content = r.json()
    first_prediction = "- name: \n" + json_content["predictions"][0]
    try:
        tasks = yaml.safe_load(first_prediction)
    except yaml.YAMLError:
        logging.error('CANNOT LOAD YAML: %s', first_prediction)
        raise
    return tasks[0]


def load_context_from_file(test_name: str, test_path: Path):
    yaml_file = test_path.parent / f"{test_name}.yaml"
    return yaml.safe_load(yaml_file.read_text())


@pytest.fixture
def call(request):
    def f(
        prompt: str, context: Optional[list[task_dict_t]] = None, context_from_file=False
    ) -> dict[str, Any]:
        if context_from_file:
            context = load_context_from_file(
                test_name=request.node.originalname, test_path=request.node.path
            )
        logging.debug('PROMPT: %s', prompt)
        payload = {
            "instances": [
                {
                    "context": yaml.dump(context),
                    "prompt": f"-name: {prompt}",
                }
            ]
        }
        r = requests.post(model_mesh_host + "/predictions/wisdom", json=payload)
        assert r.status_code

        unwrapped = unwrap_prediction(r)
        logging.info("TASK: %s", unwrapped)
        task = Task(unwrapped)
        return task

    return f
