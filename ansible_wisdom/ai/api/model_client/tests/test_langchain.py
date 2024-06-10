#!/usr/bin/env python3

from textwrap import dedent

from django.test import TestCase
from langchain.llms.fake import FakeListLLM
from langchain_core.messages.base import BaseMessage

from ansible_ai_connect.ai.api.model_client.langchain import (
    LangChainClient,
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


class TestLangChainClientNotImplemented(TestCase):
    def test_not_implemented(self):
        my_client = LangChainClient("a")

        with self.assertRaises(NotImplementedError):
            my_client.get_chat_model("a")


class TestLangChainClient(TestCase):
    def setUp(self):
        self.my_client = LangChainClient("a")

        def fake_get_chat_mode(self, model_id=None):
            return FakeListLLM(responses=["\n```\nmy_playbook```\nmy outline\n\n", "b"])

        self.my_client.get_chat_model = fake_get_chat_mode

    def test_generate_playbook(self):
        playbook, outline = self.my_client.generate_playbook(
            None,
            text="foo",
        )
        self.assertEqual(playbook, "my_playbook")
        self.assertEqual(outline, "")

    def test_generate_playbook_with_outline(self):
        playbook, outline = self.my_client.generate_playbook(None, text="foo", create_outline=True)
        self.assertEqual(playbook, "my_playbook")
        self.assertEqual(outline, "my outline")

    def test_explain_playbook(self):
        explanation = self.my_client.explain_playbook(None, content="foo")
        self.assertTrue(explanation)
