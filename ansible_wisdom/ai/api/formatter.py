import logging
import re
from io import StringIO

import yaml
from ruamel.yaml import YAML, scalarstring

logger = logging.getLogger(__name__)

"""
The code below causes any yaml.dump calls to dump None
as blank rather than "null"
"""


def represent_none(self, _):
    return self.represent_scalar('tag:yaml.org,2002:null', '')


yaml.add_representer(type(None), represent_none)


class AnsibleDumper(yaml.Dumper):
    """
    Subclass the yaml Dumper to produce Ansible-style formatting.
    - indent inner lists
    - insert blank line between top-level list elements
    - make " the proferred quote (as is done in ansible-lint)
    NOTE: this class is used to serialize/deserialize input from plugin and normalize the content in
     the same way model is trained. the plugin should send the data as is and the module will
     normalize it
    """

    def __init__(self, *args, **kwargs):
        self.first_item_ = False
        self.preferred_quote_ = '"'  # The default in ansible-lint
        super().__init__(*args, **kwargs)

    # Note when at the start of a top-level sequence so can insert a blank line before all others
    def emit(self, event):
        if isinstance(event, yaml.events.SequenceStartEvent):
            if self.indent is None or self.indent == 0:
                self.first_item_ = True
        super().emit(event)

    # Indent sequence items the same as map keys by ignoring indentless
    def increase_indent(self, flow=False, indentless=False):
        super().increase_indent(flow=flow, indentless=False)

    # Insert newline before all top-level list items except the first
    def write_indicator(self, indicator, need_whitespace, whitespace=False, indention=False):
        if self.indent == 0 and indicator == '-':
            if self.first_item_:
                self.first_item_ = False
            else:
                self.write_line_break()
        super().write_indicator(indicator, need_whitespace, whitespace, indention)

    # Copied from ansible-lint yaml_utils.py
    # Overrides ' style with " unless string already has a "
    # NOTE: doesn't generate literal '|' or folded '>' styles
    def choose_scalar_style(self):
        """Select how to quote scalars if needed."""
        style = super().choose_scalar_style()
        if style != "'":
            # block scalar, double quoted, etc.
            return style
        if '"' in self.event.value:
            return "'"
        return self.preferred_quote_

    # Prevent aliases when enhanced context adds same vars to multiple plays
    def ignore_aliases(self, data):
        return True


"""
Normalize by loading and re-serializing
"""


def normalize_yaml(yaml_str, ansible_file_type="playbook", additional_context=None):
    data = yaml.load(yaml_str, Loader=yaml.SafeLoader)
    if data is None:
        return None
    if additional_context:
        expand_vars_files(data, ansible_file_type, additional_context)
    return yaml.dump(data, Dumper=AnsibleDumper, allow_unicode=True, sort_keys=False, width=10000)


def load_and_merge_vars_in_context(vars_in_context):
    merged_vars = {}
    for v in vars_in_context:
        # Merge the vars element and the dict loaded from a vars string
        merged_vars |= yaml.load(v, Loader=yaml.SafeLoader)
    return merged_vars


def insert_set_fact_task(data, merged_vars):
    if merged_vars:
        vars_task = {
            "name": "Set variables from context",
            "ansible.builtin.set_fact": merged_vars,
        }
        data.insert(0, vars_task)


def expand_vars_playbook(data, additional_context):
    playbook_context = additional_context.get("playbookContext", {})
    var_infiles = list(playbook_context.get("varInfiles", {}).values())
    include_vars = list(playbook_context.get("includeVars", {}).values())
    merged_vars = load_and_merge_vars_in_context(var_infiles + include_vars)
    if len(merged_vars) > 0:
        for d in data:
            # last key ("tasks", "handlers", ...) needs to stay last
            # for proper placement of the prompt
            last_key = list(d.keys())[-1]
            last_key_value = d.pop(last_key)
            d["vars"] = merged_vars if "vars" not in d else (merged_vars | d["vars"])
            d[last_key] = last_key_value


def expand_vars_tasks_in_role(data, additional_context):
    role_context = additional_context.get("roleContext", {})
    role_vars = list(role_context.get("roleVars", {}).get("vars", {}).values())
    role_vars_defaults = list(role_context.get("roleVars", {}).get("defaults", {}).values())
    include_vars = list(role_context.get("includeVars", {}).values())
    merged_vars = load_and_merge_vars_in_context(role_vars_defaults + role_vars + include_vars)
    if len(merged_vars) > 0:
        insert_set_fact_task(data, merged_vars)


def expand_vars_tasks(data, additional_context):
    standalone_task_context = additional_context.get("standaloneTaskContext", {})
    include_vars = list(standalone_task_context.get("includeVars", {}).values())
    merged_vars = load_and_merge_vars_in_context(include_vars)
    if len(merged_vars) > 0:
        insert_set_fact_task(data, merged_vars)


def expand_vars_files(data, ansible_file_type, additional_context):
    """Expand the vars_files element by loading each file and add/update the vars element"""
    expand_vars_files = {
        "playbook": expand_vars_playbook,
        "tasks_in_role": expand_vars_tasks_in_role,
        "tasks": expand_vars_tasks,
    }
    if ansible_file_type in expand_vars_files:
        expand_vars_files[ansible_file_type](data, additional_context)


def preprocess(
    context,
    prompt,
    ansible_file_type="playbook",
    additional_context=None,
):
    """
    Formatting and normalization performed in this function is redundant in WCA case because
    it is already handled on the WCA side. We can safely skip it for multitask scenarios,
    which we know are WCA. No need to adopt to support both single and multitask.

    We call normalize_yaml regardless of single or multi in order to process the
    additional_context content. We need to hold the original multi-task prompt because
    pyyaml does not preserve comments.
    """
    multi_task = is_multi_task_prompt(prompt)
    original_multi_task_prompt = prompt

    """
    Add a newline between the input context and prompt in case context doesn't end with one
    """
    formatted = normalize_yaml(f'{context}\n{prompt}', ansible_file_type, additional_context)

    if formatted is not None:
        logger.debug(f'initial user input {context}\n{prompt}')

        if multi_task:
            context = formatted
            prompt = original_multi_task_prompt
        else:
            """
            Format and split off the last line as the prompt
            Append a newline to both context and prompt (as the model expects)
            """
            segs = formatted.rsplit('\n', 2)  # Last will be the final newline
            if len(segs) == 3:
                context = segs[0] + '\n'
                prompt = segs[1]
            elif len(segs) == 2:  # Context is empty
                context = ""
                prompt = segs[0]
            else:
                logger.warning(f"preprocess failed - too few new-lines in: {formatted}")

            prompt = handle_spaces_and_casing(prompt)

        logger.debug(f'preprocessed user input {context}\n{prompt}')
    return context, prompt


def handle_spaces_and_casing(prompt):
    try:
        prompt = prompt.lower()  # lowercasing the prompt always to ensure consistent results

        # before can be any leading space that might be present in `- name:` eg `      - name: `
        before, sep, after = prompt.partition('- name: ')  # keep the space at the end
        text = " ".join(after.split())  # remove additional spaces in the prompt
        prompt = f'{before}{sep}{text}'
    except Exception:
        logger.exception(f'failed to handle spacing and casing for prompt {prompt}')
        # return the prompt as is if failed to process

    return prompt


# Recursively replace Jinja2 variables with string
# values enclosed in double quotes
def handle_jinja2_variable_quotes(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            obj[key] = handle_jinja2_variable_quotes(value)
    elif isinstance(obj, list):
        for key, value in enumerate(obj):
            obj[key] = handle_jinja2_variable_quotes(value)
    elif isinstance(obj, str) and obj.startswith('{{') and obj.endswith('}}'):
        obj = scalarstring.DoubleQuotedScalarString(obj)
    return obj


def adjust_indentation(yaml):
    output = yaml
    stream = StringIO()
    with stream as fp:
        yaml_obj = YAML()
        yaml_obj.allow_duplicate_keys = True
        yaml_obj.indent(offset=2, sequence=4)
        loaded_data = yaml_obj.load(output)
        loaded_data = handle_jinja2_variable_quotes(loaded_data)
        yaml_obj.dump(loaded_data, fp)
        output = fp.getvalue()
    return output.rstrip()


def restore_indentation(yaml, original_indent):
    if yaml:
        lines = yaml.splitlines()
        first_line = lines[0]
        current_indent = len(first_line) - len(first_line.lstrip())
        if current_indent < original_indent:
            padding_level = original_indent - current_indent
            padded_lines = [" " * padding_level + line for line in lines]
            return "\n".join(padded_lines)
        elif current_indent > original_indent:
            extra_indent = current_indent - original_indent
            corrected_lines = [line[extra_indent:] for line in lines]
            return "\n".join(corrected_lines)
    return yaml


def extract_prompt_and_context(input):
    context = ''
    prompt = ''
    if input:
        _input = input.rstrip()
        segs = _input.rsplit('\n', 1)

        if len(segs) == 2:
            context = segs[0] + '\n'
            prompt = segs[1] + '\n'
        else:  # Context is empty
            context = ""
            prompt = segs[0] + '\n'
    return prompt, context


# extract full task from one or more tasks in a string
def extract_task(tasks, task_name):
    NAME = "- name: "
    splits = tasks.split(NAME)
    indent = splits[0]
    for i in range(1, len(splits)):
        if splits[i].lower().startswith(task_name.lower()):
            return f"{indent}{NAME}{splits[i].rstrip()}"
    return None


def is_multi_task_prompt(prompt):
    if prompt:
        return prompt.lstrip().startswith('#')
    return False


def strip_task_preamble_from_multi_task_prompt(prompt):
    if is_multi_task_prompt(prompt):
        prompt_split = prompt.split('#', 1)
        return f"{prompt_split[0]}# {' & '.join(get_task_names_from_prompt(prompt))}"
    return prompt


def get_task_count_from_prompt(prompt):
    task_count = 0
    if prompt:
        task_count = len(prompt.strip().split('&'))
    return task_count


def get_task_names_from_prompt(prompt):
    if is_multi_task_prompt(prompt):
        prompt = prompt.split('#', 1)[1].strip()
        split_list = prompt.split('&')
        trimmed_list = [task_prompt.strip() for task_prompt in split_list]
        fixed_list = [
            (
                trimmed_prompt.replace('- name:', '', 1).strip()
                if trimmed_prompt.startswith('- name:')
                else trimmed_prompt
            )
            for trimmed_prompt in trimmed_list
        ]
        return fixed_list
    else:
        return [prompt.split("name:")[-1].strip()]


def get_task_names_from_tasks(tasks):
    task_list = yaml.load(tasks, Loader=yaml.SafeLoader)
    if (
        not isinstance(task_list, list)
        or not isinstance(task_list[0], dict)
        or 'name' not in task_list[0]
        or not isinstance(task_list[0]['name'], str)
    ):
        raise Exception("unexpected tasks yaml")
    names = []
    for task in task_list:
        names.append(task["name"])
    return names


def restore_original_task_names(output_yaml, prompt):
    if output_yaml and is_multi_task_prompt(prompt):
        prompt_tasks = get_task_names_from_prompt(prompt)
        matches = re.finditer(r"^- name:\s+(.*)", output_yaml, re.M)
        for i, match in enumerate(matches):
            try:
                task_line = match.group(0)
                task = match.group(1)
                restored_task_line = task_line.replace(task, prompt_tasks[i])
                output_yaml = output_yaml.replace(task_line, restored_task_line)
            except IndexError:
                logger.error(
                    "There is no match for the enumerated prompt task in the suggestion yaml"
                )
                break

    return output_yaml
