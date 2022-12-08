import json
import logging
import os
import sys

import torch
# from ts.utils.util import PredictionException
from tokenizer import AnsibleTokenizer
from transformers import CodeGenForCausalLM
from ts.torch_handler.base_handler import BaseHandler

logger = logging.getLogger(__name__)


class TransformersClassifierHandler(BaseHandler):
    """
    The handler takes an input string and returns the classification text
    based on the serialized transformers checkpoint.
    """

    def __init__(self):
        super(TransformersClassifierHandler, self).__init__()
        self.initialized = False
        self.model_size = 1024
        self.max_target_length = 248

    def initialize(self, ctx):
        """Loads the model.pt file and initializes the model object.
        Instantiates Tokenizer for preprocessor to use
        Loads labels to name mapping file for post-processing inference response
        """
        self.manifest = ctx.manifest

        properties = ctx.system_properties
        model_dir = properties.get("model_dir")
        self.device = torch.device(
            "cuda:" + str(properties.get("gpu_id")) if torch.cuda.is_available() else "cpu"
        )

        # Read model serialize/pt file
        serialized_file = self.manifest["model"]["serializedFile"]
        model_pt_path = os.path.join(model_dir, serialized_file)
        if not os.path.isfile(model_pt_path):
            raise RuntimeError("Missing the model.pt or pytorch_model.bin file")

        # Load model
        self.model = CodeGenForCausalLM.from_pretrained(model_dir)
        self.model.to(self.device)
        self.model.eval()
        logger.debug('Transformer model from path {0} loaded successfully'.format(model_dir))

        # Ensure to use the same tokenizer used during training
        self.tokenizer = AnsibleTokenizer(1024)

        # Read the mapping file, index to object name
        mapping_file_path = os.path.join(model_dir, "index_to_name.json")

        if os.path.isfile(mapping_file_path):
            with open(mapping_file_path) as f:
                self.mapping = json.load(f)
        else:
            logger.warning(
                'Missing the index_to_name.json file. Inference output will not include class name.'
            )

        self.initialized = True

    def preprocess(self, data):
        """Preprocessing input request by tokenizing
        Extend with your own preprocessing steps as needed
        """
        pdata = data[0]
        prefix_prompt = '- name: '
        text = (
            self.tokenizer.bos_token
            + pdata.get("context")
            + self.tokenizer.sep_token
            + prefix_prompt
            + pdata.get("prompt").strip()
            + '\n'
        )

        tokenizer_kwargs = {'truncation': True, 'padding': 'max_length', 'max_length': 1024}
        tokenized_input = self.tokenizer(text, **tokenizer_kwargs)
        return tokenized_input

    def inference(self, inputs):
        """Predict the class of a text using a trained transformer model."""

        source_ids_ = torch.Tensor(inputs['input_ids']).long()
        source_ids_ = source_ids_.to(self.device)  # move to the core

        msg = f'''source id tensor shape: {source_ids_.shape}
        size of source id tensor {source_ids_.element_size() * source_ids_.nelement()}
        and {sys.getsizeof(source_ids_.storage())}'''
        print(msg)

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

        # TODO may be missign a few steps here between this step and tokenizer
        # output is a tensor of shape [1, ] .. so we need to get the first item
        output = self.tokenizer.tokenizer.decode(preds[0])
        result = ''
        try:
            # V2+ model output
            result = output.split(self.tokenizer.sep_token)[1].split(self.tokenizer.eos_token)[0]
        except IndexError:
            logger.error(f'failed to split ansible and endoftex token for: {output}')

        return result

    def postprocess(self, inference_output):
        return inference_output

    def handle(self, data, context):
        """
        Invoke by TorchServe for prediction request.
        Do pre-processing of data, prediction using model and postprocessing of prediciton output
        :param data: Input data for prediction
        :param context: Initial context contains model server system properties.
        :return: prediction output
        """
        model_input = self.preprocess(data)
        model_output = self.inference(model_input)
        return self.postprocess([model_output])
