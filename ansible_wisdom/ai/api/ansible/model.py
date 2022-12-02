import logging
import sys

import torch
from transformers import CodeGenForCausalLM

from ..data.data_model import Payload
from .tokenizer import AnsibleTokenizer

logger = logging.getLogger(__name__)


class AnsibleModel:
    def __init__(self, max_target_length: int = 248, model_size: int = 1024) -> None:
        self.max_target_length = max_target_length
        self.model_size = model_size
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        logger.info(f'using device {self.device}')

    def evaluate(self, payload: Payload) -> str:
        tokenized_input = self._preprocess(payload)
        result = self._predict(tokenized_input)
        return result

    def load_model(self, checkpoint):
        self.tokenizer = AnsibleTokenizer(self.model_size)

        logger.info(f'loading model from checkpoint {checkpoint}')
        self.model = CodeGenForCausalLM.from_pretrained(checkpoint)
        self.model.to(self.device)
        self.model.eval()

    def _preprocess(self, payload: Payload):
        prefix_prompt = '- name: '
        text = (
            self.tokenizer.bos_token
            + payload.context
            + self.tokenizer.sep_token
            + prefix_prompt
            + payload.prompt.strip()
            + '\n'
        )

        tokenizer_kwargs = {
            'truncation': True,
            'padding': 'max_length',
            'max_length': self.model_size,
        }
        tokenized_input = self.tokenizer(text, **tokenizer_kwargs)
        return tokenized_input

    def _predict(self, tokenized_prompt):

        source_ids_ = torch.Tensor(tokenized_prompt['input_ids']).long()
        source_ids_ = source_ids_.to(self.device)  # move to the core

        logger.info(
            f'source id tensor shape: {source_ids_.shape} \n \
            size of source id tensor \
            {source_ids_.element_size() * source_ids_.nelement()} and \
            {sys.getsizeof(source_ids_.storage())}'
        )

        source_ids_ = torch.reshape(source_ids_, (1, self.model_size))

        with torch.inference_mode():
            preds = self.model.generate(
                source_ids_,
                do_sample=False,
                num_return_sequences=1,
                temperature=0.2,
                max_new_tokens=self.max_target_length,
                top_p=0.95,
                bos_token_id=self.tokenizer.bos_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
                pad_token_id=self.tokenizer.pad_token_id,
                sep_token_id=self.tokenizer.sep_token_id,
                use_cache=True,
            )

            logger.info(f'past the prediction phase, not converting back to decoded {preds}')

        output = self.tokenizer.tokenizer.decode(preds[0])
        result = ''
        try:
            # V2+ model output
            result = output.split(self.tokenizer.sep_token)[1].split(self.tokenizer.eos_token)[0]
        except IndexError:
            logger.error(f'failed to split ansible and endoftex token for: {output}')

        return result
