import logging

from transformers import CodeGenTokenizerFast

logger = logging.getLogger(__name__)


class AnsibleTokenizer:
    def __init__(
        self,
        model_size: int,
        ckpt: str = "Salesforce/codegen-350M-mono",
        include_tabs_and_spaces: bool = False,
    ):
        self.pad_token = '<|pad|>'
        # nl, pl = 'source', 'target'
        self.bos_token = '<|startoftext|>'
        self.eos_token = '<|endoftext|>'
        self.sep_token = '<|sepoftext|>'
        self.model_size = model_size
        self.ckpt = ckpt
        self.include_tabs_and_spaces = include_tabs_and_spaces

        self.tokenizer = self._CodeGenTokenizerFast_custom(
            max_model_input_sizes=1e20,
            model_max_length=self.model_size,
            bos_token=self.bos_token,
            eos_token=self.eos_token,
            pad_token=self.pad_token,
            sep_token=self.sep_token,
        )

        self.tokenizer.padding_side = 'left'
        self.tokenizer.truncation_side = 'left'

        self.pad_token_id = self.tokenizer.get_added_vocab()[self.tokenizer.pad_token]
        self.sep_token_id = self.tokenizer.get_added_vocab()[self.tokenizer.sep_token]
        self.bos_token_id = self.tokenizer.bos_token_id
        self.eos_token_id = self.tokenizer.eos_token_id

    # make object callable
    def __call__(self, input_str, **tokenization_kwargs):
        return self.tokenizer(input_str, **tokenization_kwargs)

    def tokenize(self, text='', truncation=True, padding='max_length', max_length=512):
        tokenized_text = self.tokenizer(
            text, truncation=True, padding=padding, max_length=max_length
        )

        return tokenized_text

    def batch_decode(self, decoded_input, **kwargs):
        return self.tokenizer.batch_decode(decoded_input, **kwargs)

    def get_added_vocab(self):
        return self.tokenizer.get_added_vocab()

    # private functions start here -----------

    def _CodeGenTokenizerFast_custom(
        self,
        max_model_input_sizes: int = 1e20,
        model_max_length: int = 512,
        bos_token: str = '<|startoftext|>',
        eos_token: str = '<|endoftext|>',
        pad_token: str = '<|pad|>',
        sep_token: str = '<|sepoftext|>',
        ckpt: str = "Salesforce/codegen-350M-mono",
        include_tabs_and_spaces: bool = False,
    ):
        """this tokenizer is designed for program languge with spaces and tab tokens"""

        t = self._create_tokenizer(
            max_model_input_sizes=max_model_input_sizes,
            model_max_length=model_max_length,
            bos_token=bos_token,
            eos_token=eos_token,
            pad_token=pad_token,
            sep_token=sep_token,
            ckpt=ckpt,
        )
        if include_tabs_and_spaces:
            t = self._include_whitespace(t=t, n_min=2, n_max=32, as_special_tokens=False)
            t = self._include_tabs(t=t, n_min=2, n_max=10, as_special_tokens=False)
        return t

    def _create_tokenizer(
        self,
        max_model_input_sizes: int = 1e20,
        model_max_length: int = 256,
        bos_token: str = '<|endoftext|>',
        eos_token: str = '<|endoftext|>',
        pad_token: str = '<|endoftext|>',
        sep_token: str = '<|sepoftext|>',
        ckpt: str = "Salesforce/codegen-350M-mono",
    ):
        """Create GPT2 tokenizer, set max input size and special tokens;
        For some reason, default GPT2 tokenizer defines all special tokens
        as <|endoftext|>
        """
        t = CodeGenTokenizerFast.from_pretrained(
            ckpt,
            model_max_length=model_max_length,
            bos_token=bos_token,
            eos_token=eos_token,
            pad_token=pad_token,
            sep_token=sep_token,
        )
        t.max_model_input_sizes[ckpt] = max_model_input_sizes
        return t

    def _include_whitespace(self, t, n_min=2, n_max=20, as_special_tokens=False):
        t.add_tokens(
            [' ' * n for n in reversed(range(n_min, n_max))], special_tokens=as_special_tokens
        )
        return t

    def _include_tabs(self, t, n_min=2, n_max=20, as_special_tokens=False):
        t.add_tokens(
            ['\t' * n for n in reversed(range(n_min, n_max))], special_tokens=as_special_tokens
        )
        return t
