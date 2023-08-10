import contextlib
import logging
import timeit
from ansiblelint.rules import RulesCollection

logger = logging.getLogger(__name__)

import os
import tempfile

from copy import deepcopy
from ansiblelint.rules import RulesCollection
from ansiblelint.constants import DEFAULT_RULESDIR
from ansiblelint.config import options as default_options
from ansiblelint.runner import LintResult, _get_matches
from ansiblelint.config import Options
from ansiblelint.transformer import Transformer


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
    def __init__(self) -> None:
        self.config_options = deepcopy(default_options)
        self.config_options.write_list = ["all"]
        self.default_rules_collection = RulesCollection(rulesdirs=[DEFAULT_RULESDIR])

    def run_linter(
        self,
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

        self.config_options.lintables = [temp_completion_path]
        result = _get_matches(rules=self.default_rules_collection, options=self.config_options)
        self.run_transform(result, self.config_options)

        # read the transformed file
        with open(temp_completion_path, "r", encoding="utf-8") as yaml_file:
            transformed_completion = yaml_file.read()

        # delete the temporary file
        os.remove(temp_completion_path)

        return transformed_completion

    def run_transform(self, lint_result: LintResult, config_options: Options):
        transformer = Transformer(result=lint_result, options=config_options)
        transformer.run()