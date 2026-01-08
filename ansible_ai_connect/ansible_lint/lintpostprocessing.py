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

import logging
import os
import tempfile
from copy import deepcopy

from ansiblelint.app import get_app
from ansiblelint.config import Options
from ansiblelint.config import options as default_options
from ansiblelint.constants import DEFAULT_RULESDIR
from ansiblelint.rules import RulesCollection
from ansiblelint.runner import LintResult, get_matches
from ansiblelint.transformer import Transformer
from django.conf import settings

logger = logging.getLogger(__name__)

TEMP_TASK_FOLDER = "tasks"


class AnsibleLintCaller:
    def __init__(self) -> None:
        self.config_options = deepcopy(default_options)
        self.default_rules_collection = RulesCollection(
            app=get_app(offline=True), rulesdirs=[DEFAULT_RULESDIR]
        )
        self.config_options.write_list = settings.ANSIBLE_LINT_TRANSFORM_RULES

    def run_linter(
        self,
        inline_completion: str,
    ) -> str:
        with tempfile.TemporaryDirectory() as tmp_root:
            return self._run_linter(
                inline_completion,
                tmp_root,
            )

    def _run_linter(
        self,
        inline_completion: str,
        tmp_root: str,
    ) -> str:
        """Runs the Runner to populate a LintResult for a given snippet."""
        transformed_completion = inline_completion
        try:
            # Since the suggestions are tasks, for ansible-lint to run in write mode correctly it
            # needs to identity the temporary file as tasks file, and for that to happen the
            # temporary file needs to be be under tasks folder. Thus, creating a temporary file
            # under tasks folder.
            tmp_dir = os.path.join(tmp_root, TEMP_TASK_FOLDER)
            if os.path.isdir(tmp_dir):
                raise RuntimeError("Task directory already exists")
            os.mkdir(tmp_dir)
            with tempfile.NamedTemporaryFile(
                suffix=".yml", dir=tmp_dir, mode="w", delete=False
            ) as temp_file:
                # write the YAML string to the file
                temp_file.write(inline_completion)
                # get the path to the file
                temp_completion_path = temp_file.name

            self.config_options.lintables = [temp_completion_path]
            result = get_matches(rules=self.default_rules_collection, options=self.config_options)
            self.run_transform(result, self.config_options)

            # read the transformed file
            with open(temp_completion_path, encoding="utf-8") as yaml_file:
                transformed_completion = yaml_file.read()
        except Exception as exc:
            logger.exception(f"Lint Post-Processing resulted into exception: {exc}")
        return transformed_completion

    def run_transform(self, lint_result: LintResult, config_options: Options):
        transformer = Transformer(result=lint_result, options=config_options)
        transformer.run()
