from textwrap import dedent

from django.test import TestCase
from langchain_core.messages.base import BaseMessage

from ansible_ai_connect.ai.api.model_pipelines.langchain.pipelines import (
    unwrap_playbook_answer,
    unwrap_task_answer,
)


class TestUnwrapTaskAnswer(TestCase):
    def setUp(self):
        self.expectation = "ansible.builtin.debug:\n  msg: something went wrong"

    def test_unwrap_markdown_answer(self):
        answer = """
        I'm a model and I'm saying stuff


        ```yaml

        - name: Lapin bleu à réaction!
          ansible.builtin.debug:
            msg: something went wrong

        ```

        Some more blabla
        """
        self.assertEqual(unwrap_task_answer(dedent(answer)), self.expectation)

    def test_unwrap_markdown_with_backquotes(self):
        # e.g: llama3
        answer = """
        ```
        - name: Lapin bleu à réaction!
          ansible.builtin.debug:
            msg: something went wrong
        ```
        """
        self.assertEqual(unwrap_task_answer(dedent(answer)), self.expectation)

    def test_unwrap_just_task(self):
        answer = """
        ----
        - name: Lapin bleu à réaction!
          ansible.builtin.debug:
            msg: something went wrong



        """
        self.assertEqual(unwrap_task_answer(dedent(answer)), self.expectation)

    def test_unwrap_class_with_content_key(self):
        _content = """
        ----
        - name: Lapin bleu à réaction!
          ansible.builtin.debug:
            msg: something went wrong
        """

        class MyMessage(BaseMessage):
            pass

        message = MyMessage(content=_content, type="whatever")
        self.assertEqual(unwrap_task_answer(message), self.expectation)


class TestUnwrapPlaybookAnswer(TestCase):
    def test_unwrap_class_with_content_key(self):
        _content = """
        This is the playbook:

        ```
        - hosts: localhost
          tasks:
            - name: Lapin bleu à réaction!
              ansible.builtin.debug:
                msg: something went wrong
        ```

        This playbook will do:
        - This
        - and that
        """

        class MyMessage(BaseMessage):
            pass

        playbook, outline = unwrap_playbook_answer(_content)
        self.assertTrue(playbook.startswith("- hosts"))
        self.assertTrue(outline.startswith("This playbook"))
