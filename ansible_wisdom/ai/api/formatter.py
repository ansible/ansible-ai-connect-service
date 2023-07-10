import logging
from io import StringIO

import yaml
from ruamel.yaml import YAML, scalarstring

from .utils.jaeger import with_distributed_tracing

logger = logging.getLogger(__name__)


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


class InvalidPromptException(Exception):
    pass


"""
Normalize by loading and re-serializing
"""


def normalize_yaml(yaml_str):
    data = yaml.load(yaml_str, Loader=yaml.SafeLoader)
    if data is None:
        return None
    return yaml.dump(data, Dumper=AnsibleDumper, allow_unicode=True, sort_keys=False, width=10000)


@with_distributed_tracing(
    name="Preprocess formatter",
    description='Formats context and prompt' 'in accordance with model expectations',
    file=__file__,
    method='preprocess',
)
def preprocess(context, prompt, span_ctx):
    """
    Add a newline between the input context and prompt in case context doesn't end with one
    Format and split off the last line as the prompt
    Append a newline to both context and prompt (as the model expects)
    """
    formatted = normalize_yaml(f'{context}\n{prompt}')

    if formatted is not None:
        logger.debug(f'initial user input {context}\n{prompt}')

        segs = formatted.rsplit('\n', 2)  # Last will be the final newline
        if len(segs) == 3:
            context = segs[0] + '\n'
            prompt = segs[1]
        elif len(segs) == 2:  # Context is empty
            context = ""
            prompt = segs[0]
        else:
            logger.warn(f"preprocess failed - too few new-lines in: {formatted}")

            logger.debug(f'preprocessed user input {context}\n{prompt}')

        prompt = handle_spaces_and_casing(prompt)

        # Make sure the prompt is in the form "  - name: a string description."
        prompt_list = yaml.load(prompt, Loader=yaml.SafeLoader)
        if (
            not isinstance(prompt_list, list)
            or len(prompt_list) != 1
            or not isinstance(prompt_list[0], dict)
            or len(prompt_list[0]) != 1
            or 'name' not in prompt_list[0]
            or not isinstance(prompt_list[0]['name'], str)
        ):
            raise InvalidPromptException()

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
