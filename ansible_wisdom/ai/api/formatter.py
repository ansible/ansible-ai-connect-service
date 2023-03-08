import logging
import sys

import yaml

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


"""
Normalize by loading and re-serializing
"""


def normalize_yaml(yaml_str):
    data = yaml.load(yaml_str, Loader=yaml.SafeLoader)
    return yaml.dump(data, Dumper=AnsibleDumper, allow_unicode=True, sort_keys=False)


def preprocess(context, prompt):
    """
    Add a newline between the input context and prompt in case context doesn't end with one
    Format and split off the last line as the prompt
    Append a newline to both context and prompt (as the model expects)
    """
    try:
        formatted = normalize_yaml(f'{context}\n{prompt}')
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
    except Exception:
        # return the original prompt, context
        logger.exception(f'failed to preprocess {context}{prompt}')

    return context, prompt
