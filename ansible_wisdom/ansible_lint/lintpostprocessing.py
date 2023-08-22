import contextlib
import logging
import os
import tempfile
import timeit
from copy import deepcopy

from ansiblelint.config import Options
from ansiblelint.config import options as default_options
from ansiblelint.constants import DEFAULT_RULESDIR
from ansiblelint.rules import RulesCollection
from ansiblelint.runner import LintResult, _get_matches
from ansiblelint.transformer import Transformer
from django.conf import settings

logger = logging.getLogger(__name__)

TEMP_TASK_FOLDER = "tasks"


class AnsibleLintCaller:
    def __init__(self) -> None:
        if settings.ANSIBLE_LINT_TRANSFORM_CONFIG_OPTIONS:
            self.config_options = settings.ANSIBLE_LINT_TRANSFORM_CONFIG_OPTIONS
        else:
            self.config_options = deepcopy(default_options)
        self.config_options.write_list = ["all"]
        if settings.ANSIBLE_LINT_RULES_DIRECTORY:
            self.default_rules_collection = settings.ANSIBLE_LINT_RULES_DIRECTORY
        else:
            self.default_rules_collection = RulesCollection(rulesdirs=[DEFAULT_RULESDIR])

    def run_linter(
        self,
        inline_completion: str,
    ) -> str:
        """Runs the Runner to populate a LintResult for a given snippet."""
        tmp_dir = None
        temp_completion_path = None
        try:
            transformed_completion = inline_completion
            # Since the suggestions are tasks, for ansible-lint to run in write mode correctly it
            # needs to identity the temporary file as tasks file, and for that to happen the temporary
            # file needs to be be under tasks folder. Thus, creating a temporary file under tasks folder
            tmp_dir = os.path.join(tempfile.gettempdir(), TEMP_TASK_FOLDER)
            os.mkdir(tmp_dir)
            with tempfile.NamedTemporaryFile(
                suffix='.yml', dir=tmp_dir, mode="w", delete=False
            ) as temp_file:
                # write the YAML string to the file
                temp_file.write(inline_completion)
                # get the path to the file
                temp_completion_path = temp_file.name

            self.config_options.lintables = [temp_completion_path]
            result = _get_matches(rules=self.default_rules_collection, options=self.config_options)
            self.run_transform(result, self.config_options)

            # read the transformed file
            with open(temp_completion_path, encoding="utf-8") as yaml_file:
                transformed_completion = yaml_file.read()
        except Exception as exc:
            logger.exception(f'Lint Post-Processing resulted into exception: {exc}')
        finally:
            # delete the temporary file and tasks directory
            os.remove(temp_completion_path)
            os.rmdir(tmp_dir)
        return transformed_completion

    def run_transform(self, lint_result: LintResult, config_options: Options):
        transformer = Transformer(result=lint_result, options=config_options)
        transformer.run()
