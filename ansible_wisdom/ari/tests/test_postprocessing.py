from django.test import TestCase

from ari import postprocessing


class ARICallerTestCase(TestCase):
    def test_indent_suggestion_single_task(self):
        # "single task" suggestions get indented two extra spaces
        # relative to the "prompt indent" (spaces before the "- name:")
        single_task_suggestion = "ansible.builtin.debug:\n  msg: Hello world!"
        single_task_indented = "  ansible.builtin.debug:\n    msg: Hello world!"
        ari_caller = postprocessing.ARICaller(
            config=None,
            silent=True,
        )
        result = ari_caller.indent_suggestion(single_task_suggestion, 0)
        self.assertEqual(result, single_task_indented)

    def test_indent_suggestion_multi_task(self):
        # "multi task" suggestions DO NOT get indented two extra spaces
        # relative to the "prompt indent" (spaces before the "#")
        multi_task_suggestion = (
            "- name: Say Hello world\n  ansible.builtin.debug:\n    msg: Hello world!"
        )
        ari_caller = postprocessing.ARICaller(
            config=None,
            silent=True,
        )
        result = ari_caller.indent_suggestion(multi_task_suggestion, 0)
        self.assertEqual(result, multi_task_suggestion)
