#!/usr/bin/env python3

import logging
from textwrap import dedent
from unittest.mock import Mock

from django.test import TestCase
from langchain.llms.fake import FakeListLLM
from langchain_core.messages.base import BaseMessage

from ansible_ai_connect.ai.api.model_pipelines.langchain.pipelines import (
    LangchainCompletionsPipeline,
    LangchainPlaybookExplanationPipeline,
    LangchainPlaybookGenerationPipeline,
    unwrap_playbook_answer,
    unwrap_task_answer,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    PlaybookExplanationParameters,
    PlaybookGenerationParameters,
)
from ansible_ai_connect.test_utils import WisdomServiceLogAwareTestCase

logger = logging.getLogger(__name__)


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
        my_client = LangchainCompletionsPipeline("a")

        with self.assertRaises(NotImplementedError):
            my_client.get_chat_model("a")


class TestLangChainPlaybookGenerationPipeline(WisdomServiceLogAwareTestCase):

    def setUp(self):
        self.my_client = LangchainPlaybookGenerationPipeline("a")

        def fake_get_chat_mode(model_id=None):
            logger.debug(f"get_chat_mode: model_id={model_id}")
            return FakeListLLM(responses=["\n```\nmy_playbook```\nmy outline\n\n", "b"])

        self.my_client.get_chat_model = fake_get_chat_mode

    def test_generate_playbook(self):
        playbook, outline, warnings = self.my_client.invoke(
            PlaybookGenerationParameters.init(
                request=Mock(),
                text="foo",
            )
        )
        self.assertEqual(playbook, "my_playbook")
        self.assertEqual(outline, "")

    def test_generate_playbook_with_outline(self):
        playbook, outline, warnings = self.my_client.invoke(
            PlaybookGenerationParameters.init(request=Mock(), text="foo", create_outline=True)
        )
        self.assertEqual(playbook, "my_playbook")
        self.assertEqual(outline, "my outline")

    def test_generate_playbook_with_custom_prompt(self):
        with (
            self.assertLogs(
                logger="ansible_ai_connect.ai.api.model_pipelines.langchain.pipelines", level="INFO"
            ) as log,
        ):
            playbook, outline, warnings = self.my_client.invoke(
                PlaybookGenerationParameters.init(
                    request=Mock(),
                    text="foo",
                    create_outline=True,
                    custom_prompt="You are an Ansible expert.",
                )
            )
            self.assertInLog(
                "custom_prompt is not supported for generate_playbook and will be ignored.", log
            )
            self.assertEqual(playbook, "my_playbook")
            self.assertEqual(outline, "my outline")


class TestLangChainPlaybookExplanationPipeline(WisdomServiceLogAwareTestCase):
    def setUp(self):
        self.my_client = LangchainPlaybookExplanationPipeline("a")

        def fake_get_chat_mode(model_id=None):
            logger.debug(f"get_chat_mode: model_id={model_id}")
            return FakeListLLM(responses=["\n```\nmy_playbook```\nmy outline\n\n", "b"])

        self.my_client.get_chat_model = fake_get_chat_mode

    def test_explain_playbook(self):
        explanation = self.my_client.invoke(
            PlaybookExplanationParameters.init(request=Mock(), content="foo")
        )
        self.assertTrue(explanation)

    def test_explain_playbook_with_custom_prompt(self):
        with (
            self.assertLogs(
                logger="ansible_ai_connect.ai.api.model_pipelines.langchain.pipelines", level="INFO"
            ) as log,
        ):
            explanation = self.my_client.invoke(
                PlaybookExplanationParameters.init(
                    request=Mock(), content="foo", custom_prompt="You are an Ansible expert."
                )
            )
            self.assertInLog(
                "custom_prompt is not supported for explain_playbook and will be ignored.", log
            )
            self.assertTrue(explanation)

    def test_explain_playbook_with_model_id(self):
        with (self.assertLogs(logger=logger, level="DEBUG") as log,):
            explanation = self.my_client.invoke(
                PlaybookExplanationParameters.init(
                    request=Mock(), content="foo", model_id="mymodel"
                )
            )
            self.assertInLog("get_chat_mode: model_id=mymodel", log)
            self.assertTrue(explanation)
