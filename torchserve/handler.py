import json
import logging
import os
import sys

import torch
# from ts.utils.util import PredictionException
from transformers import CodeGenForCausalLM, CodeGenTokenizerFast
from ts.torch_handler.base_handler import BaseHandler

from anonymizor import anonymizor

logger = logging.getLogger(__name__)


class TransformersClassifierHandler(BaseHandler):
    def __init__(self):
        super(TransformersClassifierHandler, self).__init__()
        self.initialized = False
        self.model_size = 1024
        self.max_target_length = 248

    def initialize(self, ctx):
        self.manifest = ctx.manifest

        properties = ctx.system_properties
        model_dir = properties.get("model_dir")
        self.device = torch.device(
            "cuda:" + str(properties.get("gpu_id")) if torch.cuda.is_available() else "cpu"
        )

        # Read model serialize/pt file
        serialized_file = self.manifest["model"]["serializedFile"]
        serialized_file_path = os.path.join(model_dir, serialized_file)
        if not os.path.isfile(serialized_file_path):
            raise RuntimeError(f"Missing {serialized_file}")

        # Load model & tokenizer
        self.tokenizer = CodeGenTokenizerFast.from_pretrained(model_dir)
        # just to make sure truncation_side is set correctly
        self.tokenizer.truncation_side = "left"
        logger.debug(f"loading model from checkpoint {model_dir}")
        self.model = CodeGenForCausalLM.from_pretrained(model_dir)
        self.model.to(self.device)
        self.model.eval()
        logger.debug(f"Transformer model from path {model_dir} and tokenizer {self.tokenizer} loaded")

        self.initialized = True

    def preprocess(self, data):
        prefix_prompt = ""
        data_ref = data[0]
        text = self.tokenizer.bos_token + data_ref.get("context") + \
                self.tokenizer.sep_token + prefix_prompt + \
                data_ref.get("prompt").strip() + "\n"

        tokenizer_kwargs = {
            "truncation": True,
            "max_length": self.model_size
        }
        tokenized_input = self.tokenizer(text, **tokenizer_kwargs)

        return tokenized_input

    def inference(self, inputs):
        source_ids_ = torch.Tensor(inputs["input_ids"]).long()
        source_ids_len = source_ids_.shape[0]
        source_ids_ = source_ids_.to(self.device)

        print(f"source id tensor shape: {source_ids_.shape}",\
                f" size of source id tensor {source_ids_.element_size()*source_ids_.nelement()}"\
                f" and {sys.getsizeof(source_ids_.storage())}", sep="\n")

        source_ids_ = torch.unsqueeze(source_ids_, 0)

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

            logger.debug(f"past the prediction phase, not converting back to decoded {preds}")

        preds_no_context = preds[0, source_ids_len: ]
        output = self.tokenizer.decode(preds_no_context,
                skip_special_tokens=True, clean_up_tokenization_spaces=False)
        logger.debug("Token count output: %d", len(preds_no_context))

        return output

    def postprocess(self, inference_output):
        logger.debug(f"structure before PII clean up: {inference_output}")
        anonymized = anonymizor.anonymize_batch(inference_output)
        logger.debug(f"structure after PII clean up: {anonymized}")

        return anonymized

    def handle(self, data, context):
        model_input = self.preprocess(data)
        model_output = self.inference(model_input)

        return self.postprocess([model_output])
