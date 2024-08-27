#!/usr/bin/env python3

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

from ansible_ai_connect.ai.api import formatter as fmtr
from ansible_ai_connect.test_utils import WisdomServiceLogAwareTestCase


class AnsibleDumperTestCase(WisdomServiceLogAwareTestCase):
    def test_extra_empty_lines(self):
        extra_empty_lines = """---
- name: test empty lines

  copy:
    src: a
    dest: b








"""
        expected = """- name: test empty lines\n  copy:\n    src: a\n    dest: b\n"""
        output = fmtr.normalize_yaml(extra_empty_lines)
        self.assertEqual(output, expected)

    def test_extra_empty_spaces(self):
        """
        extra spaces after values, do not remove them
        """
        extra_empty_spaces = """---
- name: test empty lines

  copy:
    src: a
    dest: b

"""
        expected = """- name: test empty lines\n  copy:\n    src: a\n    dest: b\n"""
        self.assertEqual(fmtr.normalize_yaml(extra_empty_spaces), expected)

    def test_long_prompt(self):
        """
        long prompt should not be split across lines
        """
        extra_empty_spaces = """---
- name: Download https://mybackupserver.localdomain/backup.zip and extract to /tmp directory

"""
        expected = """- name: Download https://mybackupserver.localdomain/backup.zip and extract to /tmp directory\n"""  # noqa: E501
        self.assertEqual(fmtr.normalize_yaml(extra_empty_spaces), expected)

    def test_prompt_and_context(self):
        prompt_and_context = """---
- name: test empty lines

  copy:
    src: a
    dest: b



- name: here is the new prompt




"""
        expected = """- name: test empty lines\n  copy:\n    src: a\n    dest: b\n\n- name: here is the new prompt\n"""  # noqa: E501
        self.assertEqual(fmtr.normalize_yaml(prompt_and_context), expected)
        # a, b, _ = fmtr.normalize_yaml(prompt_and_context).rsplit('\n', 2)

    def test_missing_lines_between_tasks(self):
        content = """---
- name: here is the first task
  copy:
    src: a
    dest: b
- name: here is the second task
  copy:
    src: a
    dest: b
"""
        expected = """- name: here is the first task\n  copy:\n    src: a\n    dest: b\n\n- name: here is the second task\n  copy:\n    src: a\n    dest: b\n"""  # noqa: E501
        self.assertEqual(fmtr.normalize_yaml(content), expected)
        # a, b, _ = fmtr.normalize_yaml(prompt_and_context).rsplit('\n', 2)

    def test_incorrect_indent_name(self):
        """
        extra spaces after values, do not remove them
        """
        incorrect_indent_name = """---

- name: playbook with tasks indented incorrectly

  tasks:
  - name: copy tasks
    copy:
        src: a
        dest: b

"""

        expected = """- name: playbook with tasks indented incorrectly\n  tasks:\n    - name: copy tasks\n      copy:\n        src: a\n        dest: b\n"""  # noqa: E501
        self.assertEqual(fmtr.normalize_yaml(incorrect_indent_name), expected)

    def test_comments(self):
        """
        extra spaces after values, do not remove them
        """
        comments = """---
- name: test empty lines
# I am comment 0
  copy:
    src: a        # I am comment 1
    # I am comment 2
    dest: b

"""
        expected = """- name: test empty lines\n  copy:\n    src: a\n    dest: b\n"""
        self.assertEqual(fmtr.normalize_yaml(comments), expected)

    def test_restore_indentation(self):
        """
        adds necessary extra spaces if original indent > received indent
        """
        original_yaml = "  ansible.builtin.yum:\n    name: '{{ name }}'\n    state: present"
        expected = "      ansible.builtin.yum:\n        name: '{{ name }}'\n        state: present"
        self.assertEqual(fmtr.restore_indentation(original_yaml, 6), expected)

    def test_restore_indentation_two_spaces(self):
        """
        no modifications when original indent == received indent
        """
        original_yaml = "  ansible.builtin.yum:\n    name: '{{ name }}'\n    state: present"
        expected = "  ansible.builtin.yum:\n    name: '{{ name }}'\n    state: present"
        self.assertEqual(fmtr.restore_indentation(original_yaml, 2), expected)

    def test_restore_indentation_overindented(self):
        """
        removes extra spaces when original indent < received indent
        """
        original_yaml = "      ansible.builtin.dnf:\n        name: go\n        state: present\n      when: ansible_distribution == 'Fedora'"  # noqa: E501
        expected = "    ansible.builtin.dnf:\n      name: go\n      state: present\n    when: ansible_distribution == 'Fedora'"  # noqa: E501
        self.assertEqual(fmtr.restore_indentation(original_yaml, 4), expected)

    def test_casing_and_spacing_prompt(self):
        # leading space should not be removed, only spaces in the text
        prompt = "    - name:      Install NGINX        on RHEL"
        self.assertEqual("    - name: install nginx on rhel", fmtr.handle_spaces_and_casing(prompt))

        # if there is a missing space between - name: , return as is and not try to fix it
        prompt = "    - name:Install NGINX        on RHEL"
        self.assertEqual(
            "    - name:install nginx        on rhel", fmtr.handle_spaces_and_casing(prompt)
        )

    def test_adjust_indentation(self):
        """
        adjust list indentation as per ansible-lint default configuration
        """
        original_yaml = "loop:\n- 'ssh'\n- nginx\n- '{{ name }}'"
        expected = 'loop:\n  - ssh\n  - nginx\n  - "{{ name }}"'
        self.assertEqual(fmtr.adjust_indentation(original_yaml), expected)

    def test_empty_yaml(self):
        # make sure no preprocessing is performed against an empty input
        context = "---"
        prompt = ""
        context_out, prompt_out = fmtr.preprocess(context, prompt)
        self.assertEqual(context, context_out)
        self.assertEqual(prompt, prompt_out)

    def test_valid_prompt(self):
        # make sure that no exception is thrown when the prompt contains a string as the name
        context = "---"
        prompt = "  - name: This is a string"
        fmtr.preprocess(context, prompt)

    def test_extract_prompt_and_context(self):
        def run_a_test(prompt_in, context_expected, prompt_expected):
            prompt, context = fmtr.extract_prompt_and_context(prompt_in)
            self.assertEqual(prompt_expected, prompt)
            self.assertEqual(context_expected, context)

        # test standard single-task context+prompt
        PROMPT_IN = "---\n- hosts: all\n  become: yes\n\n  tasks:\n  - name: Install Apache\n"
        CONTEXT_OUT = "---\n- hosts: all\n  become: yes\n\n  tasks:\n"
        PROMPT_OUT = "  - name: Install Apache\n"

        run_a_test(PROMPT_IN, CONTEXT_OUT, PROMPT_OUT)

        # test standard multi-task context+prompt
        PROMPT_IN = "---\n- hosts: all\n  become: yes\n\n  tasks:\n  # Install Apache\n"
        CONTEXT_OUT = "---\n- hosts: all\n  become: yes\n\n  tasks:\n"
        PROMPT_OUT = "  # Install Apache\n"

        run_a_test(PROMPT_IN, CONTEXT_OUT, PROMPT_OUT)

        # test standard multi-task context+prompt with multiple tasks
        PROMPT_IN = (
            "---\n- hosts: all\n  become: yes\n\n  tasks:\n  # Install Apache & Start Apache\n"
        )
        CONTEXT_OUT = "---\n- hosts: all\n  become: yes\n\n  tasks:\n"
        PROMPT_OUT = "  # Install Apache & Start Apache\n"

        run_a_test(PROMPT_IN, CONTEXT_OUT, PROMPT_OUT)

        # test single task prompt with no additional context
        run_a_test("- name: Install Apache\n", "", "- name: Install Apache\n")

        # test multi-task prompt with no additional context
        run_a_test("# Install SSH\n", "", "# Install SSH\n")

        run_a_test(None, "", "")

    def test_extract_task(self):
        tasks = """  - name: Install ssh
    ansible.builtin.package:
      name: "{{ _name_ }}"
      state: present

  - name: Start ssh service
    ansible.builtin.service:
      name: "{{ _name_ }}"
      state: started
      enabled: true
"""
        expected_task = """  - name: Start ssh service
    ansible.builtin.service:
      name: "{{ _name_ }}"
      state: started
      enabled: true"""

        result = fmtr.extract_task(tasks, "Start ssh service")
        self.assertEqual(result, expected_task)

        result = fmtr.extract_task(tasks, "Nonexistent task")
        self.assertEqual(result, None)

    def test_is_multi_task_prompt(self):
        self.assertTrue(fmtr.is_multi_task_prompt("# Install ssh"))
        self.assertTrue(fmtr.is_multi_task_prompt("# Install ssh & Start ssh"))
        self.assertTrue(fmtr.is_multi_task_prompt("   # Install ssh"))
        self.assertFalse(fmtr.is_multi_task_prompt("- name: Install ssh"))
        self.assertFalse(fmtr.is_multi_task_prompt("Install ssh"))
        self.assertFalse(fmtr.is_multi_task_prompt(None))

    def test_get_task_count_from_prompt(self):
        self.assertEqual(0, fmtr.get_task_count_from_prompt(None))
        self.assertEqual(1, fmtr.get_task_count_from_prompt("# Install ssh"))
        self.assertEqual(2, fmtr.get_task_count_from_prompt("# Install ssh & start ssh"))
        self.assertEqual(
            3, fmtr.get_task_count_from_prompt("# Install ssh & start ssh & print hello")
        )

    def test_get_task_names_single(self):
        self.assertEqual(["Install ssh"], fmtr.get_task_names_from_prompt("- name: Install ssh"))

    def test_get_task_names_multi(self):
        self.assertEqual(["Install ssh"], fmtr.get_task_names_from_prompt("#Install ssh"))
        self.assertEqual(["Install ssh"], fmtr.get_task_names_from_prompt("# Install ssh"))
        self.assertEqual(
            ["Install ssh", "start ssh"],
            fmtr.get_task_names_from_prompt("# Install ssh & start ssh"),
        )

    def test_get_task_names_from_tasks(self):
        tasks_txt = (
            "- name:  Install Apache\n  ansible.builtin.apt:\n    name: apache2\n    "
            "state: latest\n- name:  say hello fred@example.com\n"
            "  ansible.builtin.debug:\n    msg: Hello there olivia1@example.com\n"
        )
        self.assertEqual(
            ["Install Apache", "say hello fred@example.com"],
            fmtr.get_task_names_from_tasks(tasks_txt),
        )

        with self.assertRaises(Exception, msg="unexpected tasks yaml"):
            fmtr.get_task_names_from_tasks("not well-formed tasks yaml")

    def test_load_and_merge_vars_in_context(self):
        vars_in_context = [
            """\
var1: value1
var2:
  key: value2
""",
            """\
var3: value3
""",
        ]
        expected = {"var1": "value1", "var2": {"key": "value2"}, "var3": "value3"}
        returned = fmtr.load_and_merge_vars_in_context(vars_in_context)
        self.assertEqual(expected, returned)

    def test_insert_set_fact_task(self):
        data = [{"dummy data"}]
        merged_vars = {"var1": "value1", "var2": {"key": "value2"}, "var3": "value3"}
        fmtr.insert_set_fact_task(data, merged_vars)
        self.assertEqual(2, len(data))
        self.assertTrue("name" in data[0])
        self.assertEqual(data[0]["name"], "Set variables from context")
        self.assertTrue("ansible.builtin.set_fact" in data[0])
        self.assertEqual(data[0]["ansible.builtin.set_fact"], merged_vars)

    def test_restore_original_task_names_falsy_yaml(self):
        multi_task_prompt = "# Install Apache & say hello fred@redhat.com\n"
        multi_task_yaml = "- name: \n\n - name:"
        with self.assertLogs(logger="root", level="ERROR") as log:
            fmtr.restore_original_task_names(multi_task_yaml, multi_task_prompt),
            self.assertInLog("Error while loading the result role/playbook YAML", log)

    def test_restore_original_task_names_in_role(self):
        single_task_prompt = "- name: Install ssh\n"
        multi_task_prompt = "# Install Apache & say hello fred@redhat.com\n"
        multi_task_prompt_with_loop = (
            "# Delete all virtual machines in my Azure resource group called 'melisa' that "
            "exists longer than 24 hours. Do not delete virtual machines that exists less "
            "than 24 hours."
        )
        multi_task_prompt_with_loop_extra_task = (
            "# Delete all virtual machines in my Azure resource group "
            "& say hello to ada@anemail.com"
        )

        multi_task_yaml = (
            "- name:  Install Apache\n  ansible.builtin.apt:\n    "
            "name: apache2\n    state: latest\n- name:  say hello test@example.com\n  "
            "ansible.builtin.debug:\n    msg: Hello there olivia1@example.com\n"
        )
        multi_task_yaml_extra_task = (
            "- name:  Install Apache\n  ansible.builtin.apt:\n    "
            "name: apache2\n    state: latest\n- name:  say hello test@example.com\n  "
            "ansible.builtin.debug:\n    msg: Hello there olivia1@example.com"
            "\n- name:  say hi test@example.com\n  "
            "ansible.builtin.debug:\n    msg: Hello there olivia1@example.com\n"
        )
        multi_task_yaml_with_loop = (
            "- name:  Delete all virtual machines in my "
            "Azure resource group called 'test' that exists longer than 24 hours. Do not "
            "delete virtual machines that exists less than 24 hours.\n"
            "  azure.azcollection.azure_rm_virtualmachine:\n"
            '    name: "{{ _name_ }}"\n    state: absent\n    resource_group: myResourceGroup\n'
            "    vm_size: Standard_A0\n"
            '    image: "{{ _image_ }}"\n  loop:\n    - name: "{{ vm_name }}"\n'
            '      password: "{{ _password_ }}"\n'
            '      user: "{{ vm_user }}"\n      location: "{{ vm_location }}"\n'
        )
        multi_task_yaml_with_loop_extra_task = (
            "- name:  Delete all virtual machines in my Azure resource group\n"
            "  azure.azcollection.azure_rm_virtualmachine:\n"
            '    name: "{{ _name_ }}"\n    state: absent\n    resource_group: myResourceGroup\n'
            "    vm_size: Standard_A0\n"
            '    image: "{{ _image_ }}"\n  loop:\n    - name: "{{ vm_name }}"\n'
            '      password: "{{ _password_ }}"\n'
            '      user: "{{ vm_user }}"\n      location: "{{ vm_location }}"\n'
            "- name:  say hello to ada@anemail.com\n  "
            "ansible.builtin.debug:\n    msg: Hello there olivia1@example.com\n"
        )
        single_task_yaml = (
            "  ansible.builtin.package:\n    name: openssh-server\n    state: present\n  when:\n"
            "    - enable_ssh | bool\n    - ansible_distribution == 'Ubuntu'"
        )
        expected_multi_task_yaml = (
            "- name:  Install Apache\n  ansible.builtin.apt:\n    "
            "name: apache2\n    state: latest\n- name:  say hello fred@redhat.com\n  "
            "ansible.builtin.debug:\n    msg: Hello there olivia1@example.com\n"
        )
        expected_multi_task_yaml_with_loop = (
            "- name:  Delete all virtual machines in my "
            "Azure resource group called 'melisa' that exists longer than 24 hours. Do not "
            "delete virtual machines that exists less than 24 hours.\n"
            "  azure.azcollection.azure_rm_virtualmachine:\n"
            '    name: "{{ _name_ }}"\n    state: absent\n    resource_group: myResourceGroup\n'
            "    vm_size: Standard_A0\n"
            '    image: "{{ _image_ }}"\n  loop:\n    - name: "{{ vm_name }}"\n'
            '      password: "{{ _password_ }}"\n'
            '      user: "{{ vm_user }}"\n      location: "{{ vm_location }}"\n'
        )
        expected_multi_task_yaml_with_loop_extra_task = (
            "- name:  Delete all virtual machines in my Azure resource group\n"
            "  azure.azcollection.azure_rm_virtualmachine:\n"
            '    name: "{{ _name_ }}"\n    state: absent\n    resource_group: myResourceGroup\n'
            "    vm_size: Standard_A0\n"
            '    image: "{{ _image_ }}"\n  loop:\n    - name: "{{ vm_name }}"\n'
            '      password: "{{ _password_ }}"\n'
            '      user: "{{ vm_user }}"\n      location: "{{ vm_location }}"\n'
            "- name:  say hello to ada@anemail.com\n  "
            "ansible.builtin.debug:\n    msg: Hello there olivia1@example.com\n"
        )

        self.assertEqual(
            expected_multi_task_yaml,
            fmtr.restore_original_task_names(multi_task_yaml, multi_task_prompt),
        )

        with self.assertLogs(logger="root", level="ERROR") as log:
            fmtr.restore_original_task_names(multi_task_yaml_extra_task, multi_task_prompt),
            self.assertInLog(
                "There is no match for the enumerated prompt task in the suggestion yaml", log
            )

        self.assertEqual(
            expected_multi_task_yaml_with_loop,
            fmtr.restore_original_task_names(
                multi_task_yaml_with_loop, multi_task_prompt_with_loop
            ),
        )

        self.assertEqual(
            expected_multi_task_yaml_with_loop_extra_task,
            fmtr.restore_original_task_names(
                multi_task_yaml_with_loop_extra_task, multi_task_prompt_with_loop_extra_task
            ),
        )

        self.assertEqual(
            single_task_yaml,
            fmtr.restore_original_task_names(single_task_yaml, single_task_prompt),
        )

        self.assertEqual(
            "",
            fmtr.restore_original_task_names("", multi_task_prompt),
        )

    def test_restore_original_task_names_in_playbook(self):
        payload_context = "- name: Playbook\n  hosts: all\n  tasks:\n"
        single_task_prompt = "    - name: Install ssh\n"
        multi_task_prompt = "    # Install Apache & say hello fred@redhat.com\n"
        multi_task_prompt_with_loop = (
            "    # Delete all virtual machines in my Azure resource group called 'melisa' that "
            "exists longer than 24 hours. Do not delete virtual machines that exists less "
            "than 24 hours."
        )
        multi_task_prompt_with_loop_extra_task = (
            "    # Delete all virtual machines in my Azure resource group "
            "& say hello to ada@anemail.com"
        )

        multi_task_yaml = (
            "    - name:  Install Apache\n      ansible.builtin.apt:\n        "
            "name: apache2\n        state: latest\n    - name:  say hello test@example.com\n      "
            "ansible.builtin.debug:\n        msg: Hello there olivia1@example.com\n"
        )
        multi_task_yaml_extra_task = (
            "    - name:  Install Apache\n      ansible.builtin.apt:\n        "
            "name: apache2\n        state: latest\n    - name:  say hello test@example.com\n      "
            "ansible.builtin.debug:\n        msg: Hello there olivia1@example.com"
            "\n    - name:  say hi test@example.com\n      "
            "ansible.builtin.debug:\n        msg: Hello there olivia1@example.com\n"
        )
        multi_task_yaml_with_loop = (
            "    - name:  Delete all virtual machines in my "
            "Azure resource group called 'test' that exists longer than 24 hours. Do not "
            "delete virtual machines that exists less than 24 hours.\n"
            "      azure.azcollection.azure_rm_virtualmachine:\n"
            '        name: "{{ _name_ }}"\n        state: absent\n'
            "        resource_group: myResourceGroup\n"
            "        vm_size: Standard_A0\n"
            '        image: "{{ _image_ }}"\n      loop:\n        - name: "{{ vm_name }}"\n'
            '          password: "{{ _password_ }}"\n'
            '          user: "{{ vm_user }}"\n          location: "{{ vm_location }}"\n'
        )
        multi_task_yaml_with_loop_extra_task = (
            "    - name:  Delete all virtual machines in my Azure resource group\n"
            "      azure.azcollection.azure_rm_virtualmachine:\n"
            '        name: "{{ _name_ }}"\n        state: absent\n'
            "        resource_group: myResourceGroup\n"
            "        vm_size: Standard_A0\n"
            '        image: "{{ _image_ }}"\n      loop:\n        - name: "{{ vm_name }}"\n'
            '          password: "{{ _password_ }}"\n'
            '          user: "{{ vm_user }}"\n          location: "{{ vm_location }}"\n'
            "    - name:  say hello to ada@anemail.com\n      "
            "ansible.builtin.debug:\n        msg: Hello there olivia1@example.com\n"
        )
        single_task_yaml = (
            "      ansible.builtin.package:\n        name: openssh-server\n"
            "        state: present\n      when:\n"
            "        - enable_ssh | bool\n        - ansible_distribution == 'Ubuntu'"
        )
        expected_multi_task_yaml = (
            "    - name:  Install Apache\n      ansible.builtin.apt:\n        "
            "name: apache2\n        state: latest\n    - name:  say hello fred@redhat.com\n      "
            "ansible.builtin.debug:\n        msg: Hello there olivia1@example.com\n"
        )
        expected_multi_task_yaml_with_loop = (
            "    - name:  Delete all virtual machines in my "
            "Azure resource group called 'melisa' that exists longer than 24 hours. Do not "
            "delete virtual machines that exists less than 24 hours.\n"
            "      azure.azcollection.azure_rm_virtualmachine:\n"
            '        name: "{{ _name_ }}"\n        state: absent\n'
            "        resource_group: myResourceGroup\n"
            "        vm_size: Standard_A0\n"
            '        image: "{{ _image_ }}"\n      loop:\n        - name: "{{ vm_name }}"\n'
            '          password: "{{ _password_ }}"\n'
            '          user: "{{ vm_user }}"\n          location: "{{ vm_location }}"\n'
        )
        expected_multi_task_yaml_with_loop_extra_task = (
            "    - name:  Delete all virtual machines in my Azure resource group\n"
            "      azure.azcollection.azure_rm_virtualmachine:\n"
            '        name: "{{ _name_ }}"\n        state: absent\n'
            "        resource_group: myResourceGroup\n"
            "        vm_size: Standard_A0\n"
            '        image: "{{ _image_ }}"\n      loop:\n        - name: "{{ vm_name }}"\n'
            '          password: "{{ _password_ }}"\n'
            '          user: "{{ vm_user }}"\n          location: "{{ vm_location }}"\n'
            "    - name:  say hello to ada@anemail.com\n      "
            "ansible.builtin.debug:\n        msg: Hello there olivia1@example.com\n"
        )

        self.assertEqual(
            expected_multi_task_yaml,
            fmtr.restore_original_task_names(multi_task_yaml, multi_task_prompt, payload_context),
        )

        with self.assertLogs(logger="root", level="ERROR") as log:
            fmtr.restore_original_task_names(
                multi_task_yaml_extra_task, multi_task_prompt, payload_context
            ),
            self.assertInLog(
                "There is no match for the enumerated prompt task in the suggestion yaml", log
            )

        self.assertEqual(
            expected_multi_task_yaml_with_loop,
            fmtr.restore_original_task_names(
                multi_task_yaml_with_loop, multi_task_prompt_with_loop, payload_context
            ),
        )

        self.assertEqual(
            expected_multi_task_yaml_with_loop_extra_task,
            fmtr.restore_original_task_names(
                multi_task_yaml_with_loop_extra_task,
                multi_task_prompt_with_loop_extra_task,
                payload_context,
            ),
        )

        self.assertEqual(
            single_task_yaml,
            fmtr.restore_original_task_names(single_task_yaml, single_task_prompt, payload_context),
        )

        self.assertEqual(
            "",
            fmtr.restore_original_task_names("", multi_task_prompt, payload_context),
        )

    def test_restore_original_task_names_for_index_error(self):
        # The following prompt simulates a mismatch between requested tasks and received tasks
        payload_context = "- name: Playbook\n  hosts: all\n  tasks:\n"
        multi_task_prompt = "# Install Apache\n"
        multi_task_yaml = (
            "    - name:  Install Apache\n      ansible.builtin.apt:\n        "
            "name: apache2\n        state: latest\n    - name:  say hello test@example.com\n      "
            "ansible.builtin.debug:\n        msg: Hello there olivia1@example.com\n"
        )

        with self.assertLogs(logger="root", level="ERROR") as log:
            fmtr.restore_original_task_names(multi_task_yaml, multi_task_prompt, payload_context)
            self.assertInLog(
                "There is no match for the enumerated prompt task in the suggestion yaml", log
            )

    def test_restore_original_task_names_for_task_inclusions(self):
        payload_context = "- name: Playbook\n  hosts: all\n  tasks:\n"
        multi_task_prompt = (
            "# use include_tasks and task file install_pkg.yml, install git, tree and wget\n"
        )
        multi_task_yaml = (
            "    - include_tasks: install_pkg.yml\n      loop:\n"
            "        - git\n        - wget\n        - tree\n"
        )

        self.assertEqual(
            multi_task_yaml,
            fmtr.restore_original_task_names(multi_task_yaml, multi_task_prompt, payload_context),
        )

    def test_restore_original_task_names_for_playbook_with_task_preset(self):
        payload_context = (
            "- name: Playbook\n  hosts: all\n  tasks:\n"
            "    - name:  Install Apache\n      ansible.builtin.apt:\n        "
            "name: apache2\n        state: latest\n"
        )
        multi_task_prompt = "# say hello test@example.com\n"

        multi_task_yaml = (
            "    - name:  say hello test@example.com\n      "
            "ansible.builtin.debug:\n        msg: Hello there olivia1@example.com\n"
        )

        self.assertEqual(
            multi_task_yaml,
            fmtr.restore_original_task_names(multi_task_yaml, multi_task_prompt, payload_context),
        )

    def test_strip_task_preamble_from_multi_task_prompt_no_preamble_unchanged_multi(self):
        prompt = "    # install ffmpeg"
        self.assertEqual(prompt, fmtr.strip_task_preamble_from_multi_task_prompt(prompt))

    def test_strip_task_preamble_from_multi_task_prompt_no_preamble_unchanged_single(self):
        prompt = "    - name: install ffmpeg"
        self.assertEqual(prompt, fmtr.strip_task_preamble_from_multi_task_prompt(prompt))

    def test_strip_task_preamble_from_multi_task_prompt_one_preamble_changed(self):
        before = "    # - name: install ffmpeg"
        after = "    # install ffmpeg"
        self.assertEqual(after, fmtr.strip_task_preamble_from_multi_task_prompt(before))

    def test_strip_task_preamble_from_multi_task_prompt_two_preambles_changed(self):
        before = "    # - name: install ffmpeg & - name: start ffmpeg"
        after = "    # install ffmpeg & start ffmpeg"
        self.assertEqual(after, fmtr.strip_task_preamble_from_multi_task_prompt(before))

    def test_strip_task_preamble_from_multi_task_prompt_remove_upper_case(self):
        before = "    # - name: install ffmpeg & - name: start FFMPEG"
        after = "    # install ffmpeg & start ffmpeg"
        self.assertEqual(after, fmtr.strip_task_preamble_from_multi_task_prompt(before))

    def test_unify_prompt_ending(self):
        before = "    # Install go & Install nginx & Install git :"
        after = "    # Install go & Install nginx & Install git\n"
        self.assertEqual(after, fmtr.unify_prompt_ending(before))

    def test_unify_prompt_ending_with_colon_and_with_new_line(self):
        before = "    # Install go & Install nginx & Install git :\n"
        after = "    # Install go & Install nginx & Install git\n"
        self.assertEqual(after, fmtr.unify_prompt_ending(before))

    def test_unify_prompt_ending_with_colon_end_with_spaces(self):
        before = "    # Install go & Install nginx & Install git :    "
        after = "    # Install go & Install nginx & Install git\n"
        self.assertEqual(after, fmtr.unify_prompt_ending(before))

    def test_unify_prompt_ending_with_spaces_and_end_of_line(self):
        before = "    # Install go & Install git :    \n"
        after = "    # Install go & Install git\n"
        self.assertEqual(after, fmtr.unify_prompt_ending(before))

    def test_unify_prompt_ending_with_sticked_colon(self):
        before = "    # Install go & Install nginx & Install git:"
        after = "    # Install go & Install nginx & Install git\n"
        self.assertEqual(after, fmtr.unify_prompt_ending(before))

    def test_unify_prompt_ending_with_singl_task(self):
        before = "    # Install go :\n"
        after = "    # Install go\n"
        self.assertEqual(after, fmtr.unify_prompt_ending(before))

    def test_unify_prompt_ending_with_doubled_colon(self):
        before = "    # Install go & Install nginx & Install git::"
        after = "    # Install go & Install nginx & Install git\n"
        self.assertEqual(after, fmtr.unify_prompt_ending(before))

    def test_unify_prompt_ending_with_doubled_colon_and_spaces(self):
        before = "    # Install go & Install nginx & Install git :  :\n"
        after = "    # Install go & Install nginx & Install git\n"
        self.assertEqual(after, fmtr.unify_prompt_ending(before))

    def test_unify_prompt_ending_with_fully_valid_string(self):
        before = "  # Install go & Install nginx & Install git"
        after = "  # Install go & Install nginx & Install git\n"
        self.assertEqual(after, fmtr.unify_prompt_ending(before))

    def test_unify_prompt_ending_empty_string(self):
        before = ""
        after = "\n"
        self.assertEqual(after, fmtr.unify_prompt_ending(before))

    def test_unify_prompt_ending_whitespaces_string(self):
        before = "   \n \t:  \n \t:: "
        after = "\n"
        self.assertEqual(after, fmtr.unify_prompt_ending(before))

    def test_get_fqcn_module_from_prediction(self):
        self.assertEqual(
            "ansible.builtin.package",
            fmtr.get_fqcn_or_module_from_prediction(
                "      ansible.builtin.package:\n"
                "        name: docker\n"
                "        state: present\n"
            ),
        )
        self.assertEqual(
            "ansible.builtin.import_tasks",
            fmtr.get_fqcn_or_module_from_prediction(
                "      ansible.builtin.import_tasks: first_basic_.yml\n"
            ),
        )
        self.assertEqual(
            "ansible.builtin.include_tasks",
            fmtr.get_fqcn_or_module_from_prediction(
                "      ansible.builtin.include_tasks:\n" "        file: ../common/tasks/setup.yml\n"
            ),
        )
        self.assertEqual(
            "community.general.s3_facts",
            fmtr.get_fqcn_or_module_from_prediction(
                "      community.general.s3_facts:\n"
                "        bucket: my-ansible-bucket\n"
                "        object: /my-ansible-bucket/requirements.txt\n"
                "        mode: get\n"
            ),
        )
        self.assertEqual(
            "ansible.builtin.include_role",
            fmtr.get_fqcn_or_module_from_prediction(
                "      ansible.builtin.include_role:\n"
                "        name: redhat.rhel_system_roles.cockpit\n"
            ),
        )
        self.assertEqual(
            "docker_image",
            fmtr.get_fqcn_or_module_from_prediction(
                "      docker_image:\n"
                "        name: rabbitmq:3.7.13\n"
                "        source: pull\n"
                "      when: image_facts.images | length == 0\n"
            ),
        )
        self.assertEqual(
            "servicenow.itsm.change_info",
            fmtr.get_fqcn_or_module_from_prediction(
                "      servicenow.itsm.change_info:\n"
                '        sys_id: "{{ item.sys_id }}"\n'
                "        register: change_info\n"
                '        loop: "{{ change_list }}"\n'
            ),
        )
        self.assertEqual(
            "ansible.builtin.include_role",
            fmtr.get_fqcn_or_module_from_prediction(
                "      ansible.builtin.include_role:\n"
                "          name: pcs.azure.recovery_services_vault\n"
                "        vars:\n"
                "          recovery_service_vault_resource_group: "
                '"{{ resource_group_name.sys_id }}"\n'
                "          recovery_service_vault_name: "
                '"{{ recovery_service_vault_name.sys_id }}"\n'
                "          recovery_service_vault_state: absent\n"
            ),
        )
        self.assertEqual(
            "community.general.maven_map",
            fmtr.get_fqcn_or_module_from_prediction(
                "      community.general.maven_map:\n"
                "        name: dto\n"
                "        version: 3d38c886-0c6d-4b1a-907e-76a0b9a8f996\n"
                "        repository_url: https://repo.maven.org/maven2\n"
                "        state: present\n"
            ),
        )
        self.assertEqual(
            "community.general.maven_map",
            fmtr.get_fqcn_or_module_from_prediction(
                "      community.general.maven_map:\n"
                "        name: dto\n"
                "        version: 1\n"
                "        repository_url: https://repo.maven.org/maven2:1234\n"
                "        state: present\n"
            ),
        )
        self.assertEqual(
            "community.general.maven_map",
            fmtr.get_fqcn_or_module_from_prediction(
                "      community.general.maven_map:\n"
                "        name: dto\n"
                "        version: 1\n"
                '        repository_url: https://repo.maven.org/maven2:"{{ port }}"\n'
                "        state: present\n"
            ),
        )
        self.assertEqual(
            "amazon.aws.ec2_vpc_api",
            fmtr.get_fqcn_or_module_from_prediction(
                "      amazon.aws.ec2_vpc_api:\n"
                "          state: present\n"
                "        subnets:\n"
                "          cidr: 00.01.0.99/24\n"
                "          az: us-east-1r\n"
            ),
        )

    def test_get_fqcn_module_from_prediction_none(self):
        self.assertIsNone(fmtr.get_fqcn_or_module_from_prediction(None))

    def test_get_ansible_task_keywords(self):
        keywords = fmtr.get_ansible_task_keywords()
        self.assertTrue("loop" in keywords)
        self.assertTrue("action" in keywords)
        self.assertTrue("async" in keywords)
        self.assertTrue("become_method" in keywords)
        self.assertTrue("collections" in keywords)
        self.assertTrue("connection" in keywords)
        self.assertTrue("delay" in keywords)
        self.assertTrue("no_log" in keywords)
        self.assertTrue("when" in keywords)
        self.assertTrue("tags" in keywords)
        self.assertTrue("timeout" in keywords)

    def test_get_fqcn_module_from_prediction_with_task_keywords(self):
        self.assertEqual(
            "community.windows.win_iis_website",
            fmtr.get_fqcn_or_module_from_prediction(
                "      loop:\n"
                "        - 8080\n"
                "        - 8081\n"
                "      community.windows.win_iis_website:\n"
                '        name: "name1"\n'
                "        state: started\n"
            ),
        )
        self.assertEqual(
            "community.windows.win_iis_website",
            fmtr.get_fqcn_or_module_from_prediction(
                "      community.windows.win_iis_website:\n"
                '        name: "name1"\n'
                "        state: started\n"
                "      loop:\n"
                "        - 8080\n"
                "        - 8081\n"
            ),
        )
        self.assertEqual(
            "win_iis_website",
            fmtr.get_fqcn_or_module_from_prediction(
                "      loop:\n"
                "        - 8080\n"
                "        - 8081\n"
                "      win_iis_website:\n"
                '        name: "name1"\n'
                "        state: started\n"
            ),
        )
        self.assertEqual(
            "win_iis_website",
            fmtr.get_fqcn_or_module_from_prediction(
                "      win_iis_website:\n"
                '        name: "name1"\n'
                "        state: started\n"
                "      loop:\n"
                "        - 8080\n"
                "        - 8081\n"
            ),
        )
        self.assertEqual(
            "win_iis_website",
            fmtr.get_fqcn_or_module_from_prediction(
                "      timeout: 200\n"
                "      win_iis_website:\n"
                '        name: "name1"\n'
                "        state: started\n"
            ),
        )


if __name__ == "__main__":
    tests = AnsibleDumperTestCase()
    tests.test_extra_empty_lines()
    tests.test_extra_empty_spaces()
    tests.test_incorrect_indent_name()
    tests.test_comments()
    tests.test_prompt_and_context()
    tests.test_restore_indentation()
    tests.test_casing_and_spacing_prompt()
    tests.test_adjust_indentation()
    tests.test_empty_yaml()
    tests.test_valid_prompt()
    tests.test_list_as_name()
    tests.test_dict_as_name()
    tests.test_extract_prompt_and_context()
    tests.test_extract_task()
    tests.test_is_multi_task_prompt()
    tests.test_get_task_count_from_prompt()
    tests.test_get_task_names_from_tasks()
    tests.test_get_task_names_single()
    tests.test_get_task_names_multi()
    tests.test_load_and_merge_vars_in_context()
    tests.test_insert_set_fact_task()
    tests.test_restore_original_task_names()
    tests.test_strip_task_preamble_from_multi_task_prompt_no_preamble_unchanged_multi()
    tests.test_strip_task_preamble_from_multi_task_prompt_no_preamble_unchanged_single()
    tests.test_strip_task_preamble_from_multi_task_prompt_one_preamble_changed()
    tests.test_strip_task_preamble_from_multi_task_prompt_two_preambles_changed()
    tests.test_get_fqcn_module_from_prediction()
    tests.test_get_fqcn_module_from_prediction_none()
    tests.test_get_ansible_task_keywords()
    tests.test_get_fqcn_module_from_prediction_with_task_keywords()
