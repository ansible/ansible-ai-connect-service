#!/usr/bin/env python3

from ai.api import formatter as fmtr
from django.test import TestCase


class AnsibleDumperTestCase(TestCase):
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
        self.assertEqual('    - name: install nginx on rhel', fmtr.handle_spaces_and_casing(prompt))

        # if there is a missing space between - name: , return as is and not try to fix it
        prompt = "    - name:Install NGINX        on RHEL"
        self.assertEqual(
            '    - name:install nginx        on rhel', fmtr.handle_spaces_and_casing(prompt)
        )

    def test_adjust_indentation(self):
        """
        adjust list indentation as per ansible-lint default configuration
        """
        original_yaml = "loop:\n- 'ssh'\n- nginx\n- '{{ name }}'"
        expected = "loop:\n  - ssh\n  - nginx\n  - \"{{ name }}\""
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

    def test_list_as_name(self):
        # make sure that an exception is thrown when the prompt contains a list as the name
        context = "---"
        prompt = "  - name: [This is a list]"
        with self.assertRaises(Exception):
            fmtr.preprocess(context, prompt)

    def test_dict_as_name(self):
        # make sure that an exception is thrown when the prompt contains a dictionary as the name
        context = "---"
        prompt = "  - name: {This is a dict}"
        with self.assertRaises(Exception):
            fmtr.preprocess(context, prompt)


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
