#!/usr/bin/env python3

import logging
from textwrap import dedent
from unittest.mock import Mock

from django.test import TestCase
from langchain_community.llms import FakeListLLM
from langchain_core.messages.base import BaseMessage

from ansible_ai_connect.ai.api.model_pipelines.langchain.configuration import (
    LangchainConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.langchain.pipelines import (
    LangchainCompletionsPipeline,
    LangchainPlaybookExplanationPipeline,
    LangchainPlaybookGenerationPipeline,
    LangchainRoleGenerationPipeline,
    unwrap_message_with_yaml_answer,
    unwrap_playbook_answer,
    unwrap_role_answer,
    unwrap_task_answer,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    PlaybookExplanationParameters,
    PlaybookGenerationParameters,
    RoleGenerationParameters,
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

        playbook, outline = unwrap_playbook_answer(_content)
        self.assertTrue(playbook.startswith("- hosts"))
        self.assertTrue(outline.startswith("This playbook"))


class TestUnwrapRoleAnswer(TestCase):
    _first_request_content = """
Role name: vpc_subnet_ec2

tasks/main.yml

---
# Tasks for AWS VPC Creation, Subnet Creation and EC2 Instance Deployment

```yaml
# Define the AWS region
- aws_region: "us-west-2"
 tags:
    Name: "{{ ansible_playbook_name }}-region"

# Attach the internet gateway to VPC
- name: Attach Internet Gateway to VPC
 aws_eip_association:
    eip: "{{ igw.internet_gateways[0].id }}"
    vpc: "{{ vpc.vpcs[0].id }}"
    state: present

# Print the EC2 instance ID for verification
- name: Display EC2 Instance ID
  debug: var = ec2_instance.instances[0].id

```
"""
    _second_request_content = """
# defaults/main.yml

```yaml
# Set default AWS region if not provided in the inventory file
aws_region: "us-west-2"
```
"""
    _expected_second_request_content = unwrap_message_with_yaml_answer(_second_request_content)
    _wrong_role_name_format = """
```yaml
---
# Role Name: Preparing_VPC

# Tasks:
 - name: Create VPC
   ec2_vpc:
     cidr_block: 10.0.0.0/16
     region: us-east-1
     tags:
       Name: MyVPC

 - name: Create EC2 Instance
   ec2_instance:
     subnet_id: "{{ vpcs.vpcs[0].subnets[0] }}"
     region: us-east-1
     image_id: ami-0a42b56c7d8e9f01
     instance_type: t2.micro
     wait: yes
     tags:
       Name: MyEC2
```
"""

    _content_without_yaml = """
# Role Name: amazon-vpc-ec2-deploy

   ---
   # Main file for tasks in amazon-vpc-ec2-deploy role.

   - name: Create VPC
     aws_vpc:
       state: present
       cidr_block: 10.0.0.0/16
       tags:
         Name: my-vpc

   - name: Wait for EC2 instance to be ready
     wait_for:
       delay: 10
       timeout: 600
       seconds: 300
     when: ec2_instance is defined and ec2_instance.instance_id is defined
"""

    def test_unwrap_wrong_role(self):
        role, files, outline = unwrap_role_answer(self._wrong_role_name_format, False)
        self.assertEqual(role, "role_name")
        self.assertTrue(files[0]["content"].startswith("---"))
        self.assertTrue(files[0]["content"].endswith("Name: MyEC2"))
        self.assertEqual(-1, files[0]["content"].find("```"))
        self.assertEqual(-1, files[0]["content"].find("yaml"))
        self.assertEqual(outline, "")

    def test_role_without_yaml(self):
        role, files, outline = unwrap_role_answer(self._content_without_yaml, False)
        self.assertEqual(role, "amazon-vpc-ec2-deploy")
        self.assertTrue(files[0]["content"].startswith("---"))
        self.assertTrue(files[0]["content"].endswith("is defined"))
        self.assertEqual(outline, "")

    def test_unwrap_role(self):
        role, files, outline = unwrap_role_answer(self._first_request_content, True)
        self.assertEqual(role, "vpc_subnet_ec2")
        self.assertTrue(files[0]["content"].startswith("# Define"))
        self.assertTrue(files[0]["content"].endswith("ec2_instance.instances[0].id"))
        self.assertEqual(-1, files[0]["content"].find("```"))
        self.assertEqual(-1, files[0]["content"].find("yaml"))
        self.assertEqual(
            outline,
            """1. Attach Internet Gateway to VPC
2. Display EC2 Instance ID
""",
        )


class TestLangChainClientNotImplemented(TestCase):
    def test_not_implemented(self):
        my_client = LangchainCompletionsPipeline(
            LangchainConfiguration(
                inference_url="http://localhost", model_id="a-model-id", timeout=None
            )
        )

        with self.assertRaises(NotImplementedError):
            my_client.get_chat_model("a")


class TestLangChainPlaybookGenerationPipeline(WisdomServiceLogAwareTestCase):

    def setUp(self):
        self.my_client = LangchainPlaybookGenerationPipeline(
            LangchainConfiguration(
                inference_url="http://localhost", model_id="a-model-id", timeout=None
            )
        )

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


class TestLangChainRoleGenerationPipeline(WisdomServiceLogAwareTestCase):

    _first_call = True

    def setUp(self):
        self._first_call = True
        self.my_client = LangchainRoleGenerationPipeline(
            LangchainConfiguration(
                inference_url="http://localhost", model_id="a-model-id", timeout=None
            )
        )

        def fake_get_chat_mode(model_id=None):

            logger.debug(f"get_chat_mode: model_id={model_id}")
            if self._first_call:
                self._first_call = False
                return FakeListLLM(responses=[TestUnwrapRoleAnswer._first_request_content, ""])
            else:
                return FakeListLLM(responses=[TestUnwrapRoleAnswer._second_request_content, ""])

        self.my_client.get_chat_model = fake_get_chat_mode

    def test_generate_role(self):
        role, files, outline, warnings = self.my_client.invoke(
            RoleGenerationParameters.init(
                request=Mock(),
                text="foo",
                create_outline=False,
            )
        )
        self.assertEqual(role, "vpc_subnet_ec2")
        self.assertEqual(files[1]["content"], TestUnwrapRoleAnswer._expected_second_request_content)
        self.assertEqual(outline, "")
        self.assertEqual(warnings, [])

    def test_generate_role_with_outline(self):
        role, files, outline, warnings = self.my_client.invoke(
            RoleGenerationParameters.init(
                request=Mock(),
                text="foo",
                create_outline=True,
            )
        )
        self.assertEqual(role, "vpc_subnet_ec2")
        self.assertEqual(files[1]["content"], TestUnwrapRoleAnswer._expected_second_request_content)
        self.assertEqual(
            outline,
            """1. Attach Internet Gateway to VPC
2. Display EC2 Instance ID
""",
        )
        self.assertEqual(warnings, [])


class TestLangChainPlaybookExplanationPipeline(WisdomServiceLogAwareTestCase):
    def setUp(self):
        self.my_client = LangchainPlaybookExplanationPipeline(
            LangchainConfiguration(
                inference_url="http://locahost", model_id="a-model-id", timeout=None
            )
        )

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
