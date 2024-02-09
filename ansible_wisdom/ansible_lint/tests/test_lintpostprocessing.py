import os
import shutil
import tempfile
from multiprocessing.pool import ThreadPool

from ansible_wisdom.ansible_lint.lintpostprocessing import (
    TEMP_TASK_FOLDER,
    AnsibleLintCaller,
)
from ansible_wisdom.test_utils import WisdomServiceLogAwareTestCase

normal_sample_yaml = """---
- name: Hello World Sample
  hosts: all
  tasks:
    - name: Hello Message
      debug:
        msg: "Hello World!"
"""

error_sample_yaml = """---
- name: Hello World Sample
  hosts: all
  tasks:
    - name: Hello Message
      debug; # <-- a semi-colon is inserted intentionally
        msg: "Hello World!"
"""


class TestLintPostprocessing(WisdomServiceLogAwareTestCase):
    """Test AnsibleLintCaller that is used for ansible-lint postprocessing"""

    def setUp(self):
        self.ansibleLintCaller = AnsibleLintCaller()

    def test_ansible_lint_caller(self):
        """Run a normal case"""
        result = self.ansibleLintCaller.run_linter(normal_sample_yaml)
        self.assertIsNotNone(result)

    def test_ansible_lint_caller_with_error(self):
        """Run an error case"""
        with self.assertLogs(logger='root', level='ERROR') as log:
            result = self.ansibleLintCaller.run_linter(error_sample_yaml)
            self.assertIsNotNone(result)
            self.assertInLog(
                "ruamel.yaml.scanner.ScannerError: while scanning a simple key",
                log,
            )

    def test_multi_thread(self):
        """Invoke AnsibleLintCaller in multi-thread."""

        def run_lint():
            AnsibleLintCaller().run_linter(normal_sample_yaml)

        with self.assertLogs(logger='root', level='DEBUG') as log:
            with ThreadPool(5) as pool:
                for _ in range(5):
                    pool.apply(run_lint)
            self.assertNotInLog(
                "RuntimeError: Task directory already exists",
                log,
            )

    def test_multi_thread_with_error(self):
        """Invoke AnsibleLintCaller in multi-thread with a fixed work directory."""

        def run_lint_in_a_fixed_dir():
            AnsibleLintCaller()._run_linter(normal_sample_yaml, tempfile.tempdir)

        try:
            with self.assertLogs(logger='root', level='ERROR') as log:
                with ThreadPool(5) as pool:
                    for _ in range(5):
                        pool.apply(run_lint_in_a_fixed_dir)
                self.assertInLog(
                    "RuntimeError: Task directory already exists",
                    log,
                )
        finally:
            task_dir = os.path.join(tempfile.tempdir, TEMP_TASK_FOLDER)
            if os.path.isdir(task_dir):
                shutil.rmtree(task_dir)
