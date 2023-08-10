import contextlib
import json
import logging
import timeit
from ansiblelint.rules import RulesCollection
import yaml
from ansible_risk_insight.scanner import ARIScanner
from django.conf import settings

logger = logging.getLogger(__name__)

import os
import tempfile

from copy import deepcopy
from ansiblelint.rules import RulesCollection
from ansiblelint.runner import Runner
from ansiblelint.constants import DEFAULT_RULESDIR
from ansiblelint.config import options as default_options
from ansiblelint.runner import LintResult, _get_matches
from ansiblelint.file_utils import Lintable
from ansiblelint.config import Options
from ansiblelint.transformer import Transformer
from pprint import pprint


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


class AnsibleLintCaller:
    def run_linter(
        self,
        config_options: Options,
        default_rules_collection: RulesCollection,
        inline_completion: str,
    ) -> str:
        """Runs the Runner to populate a LintResult for a given snippet."""

        transformed_completion = inline_completion

        # create a temporary file
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".yml"
        ) as temp_file:
            # write the YAML string to the file
            temp_file.write(inline_completion)
            # get the path to the file
            temp_completion_path = temp_file.name

        config_options.lintables = [temp_completion_path]
        result = _get_matches(rules=default_rules_collection, options=config_options)
        # lintable = Lintable(temp_completion_path, kind="playbook")
        # result = Runner(lintable, rules=default_rules_collection).run()
        self.run_transform(result, config_options)

        # read the transformed file
        with open(temp_completion_path, "r", encoding="utf-8") as yaml_file:
            transformed_completion = yaml_file.read()

        # delete the temporary file
        os.remove(temp_completion_path)

        return transformed_completion

    def run_transform(self, lint_result: LintResult, config_options: Options):
        transformer = Transformer(result=lint_result, options=config_options)
        transformer.run()