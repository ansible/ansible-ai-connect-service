import json
import logging
import os

import boto3
import requests
import sagemaker
from rest_framework.response import Response
from sagemaker.huggingface import HuggingFaceModel, get_huggingface_llm_image_uri
from sagemaker.huggingface.model import HuggingFacePredictor

from .base import ModelMeshClient

logger = logging.getLogger(__name__)

"""
    This AWS SageMaker module relies on the SageMaker Huggingface Inference Toolkit.
    See https://github.com/aws/sagemaker-huggingface-inference-toolkit
"""

class AWSSageMakerDeployer():
    sm_role_name = os.getenv("SM_ROLE_NAME", None)
    sm_model_id = os.getenv("HF_MODEL_ID", "ibm-granite/granite-20b-code-instruct")
    sm_num_gpus = os.getenv("HF_NUM_GPUS", 4)
    sm_instance_type = os.getenv("SM_INSTANCE_TYPE", 'ml.g4dn.12xlarge')
    sm_model_quantize = os.getenv("HF_MODEL_QUANTIZE", 'bitsandbytes')

    def __init__(self):

        self.predictor = None
        try:
            # Get th default execution role (from sagemaker's session) for the  runtime environment, if this runs
            # in a sagemaker notebook.
            role = sagemaker.get_execution_role()
        except ValueError:
            # Otherwise let's go via env configuration.
            if self.sm_role_name is None:
                raise ValueError("AWS SageMaker Role Name not set")
            iam = boto3.client('iam')
            role = iam.get_role(RoleName=self.sm_role_name)['Role']['Arn']

        # Hub Model configuration. https://huggingface.co/models
        hub = {
            'HF_MODEL_ID': self.sm_model_id,
            'SM_NUM_GPUS': json.dumps(self.sm_num_gpus),
        }
        if self.sm_model_quantize is not None:
            hub['HF_MODEL_QUANTIZE'] = self.sm_model_quantize

        # https://sagemaker.readthedocs.io/en/stable/frameworks/huggingface/sagemaker.huggingface.html#hugging-face-model
        self.huggingface_model = HuggingFaceModel(
            image_uri=get_huggingface_llm_image_uri("huggingface", version="2.0.2"),
            env=hub,
            role=role,
        )

    def deploy(self,
               endpoint_name=None,
               initial_instance_count=1,
               instance_type=sm_instance_type,
               endpoint_type=None,
               container_startup_health_check_timeout=300):

        # deploy model to SageMaker Inference
        self.predictor = self.huggingface_model.deploy(
            endpoint_name=endpoint_name,
            endpoint_type=endpoint_type,
            initial_instance_count=initial_instance_count,
            instance_type=instance_type,
            container_startup_health_check_timeout=container_startup_health_check_timeout,
        )

    def shutdown(self):
        if self.predictor is None:
            raise ValueError
        self.predictor.delete_model()
        self.predictor.delete_endpoint()


class AWSSageMakerClient(ModelMeshClient):
    def __init__(self, inference_url):
        """Creates a SageMaker Predictor instance`.
           See https://sagemaker.readthedocs.io/en/stable/frameworks/huggingface/sagemaker.huggingface.html#hugging-face-predictor
            Requisite:
                Ensure an AWS SageMaker token/session is available on the runtime.
            Args:
                inference_url (str): The SageMaker endpoint name
        """
        super().__init__(inference_url=inference_url)
        self.session = requests.Session()
        self.headers = {"Content-Type": "application/json"}
        self.sm_session = sagemaker.Session()

        self.predictor = HuggingFacePredictor(
            endpoint_name=inference_url,
            sagemaker_session=self.sm_session,
            # serializer=JSONSerializer(),
            # deserializer=JSONDeserializer(),
        )

    def infer(self, model_input, **kwargs) -> Response:
        """
            As of today the TGI supports the following parameters:
                temperature: Controls randomness in the model. Lower values will make the model more deterministic and higher values will make the model more random. Default value is 1.0.
                max_new_tokens: The maximum number of tokens to generate. Default value is 20, max value is 512.
                repetition_penalty: Controls the likelihood of repetition, defaults to null.
                seed: The seed to use for random generation, default is null.
                stop: A list of tokens to stop the generation. The generation will stop when one of the tokens is generated.
                top_k: The number of highest probability vocabulary tokens to keep for top-k-filtering. Default value is null, which disables top-k-filtering.
                top_p: The cumulative probability of parameter highest probability vocabulary tokens to keep for nucleus sampling, default to null
                do_sample: Whether or not to use sampling ; use greedy decoding otherwise. Default value is false.
                best_of: Generate best_of sequences and return the one if the highest token logprobs, default to null.
                details: Whether or not to return details about the generation. Default value is false.
                return_full_text: Whether or not to return the full text or only the generated part. Default value is false.
                truncate: Whether or not to truncate the input to the maximum length of the model. Default value is true.
                typical_p: The typical probability of a token. Default value is null.
                watermark: The watermark to use for the generation. Default value is false.
            """
        input = model_input.get("instances", [{}])[0]
        response = self.predictor.predict({
            "inputs": input,
            "parameters": {
                "do_sample": True,
                "top_p": 0.7,
                "temperature": 0.7,
                "top_k": 50,
                "max_new_tokens": 256,
                "repetition_penalty": 1.03,
            }
        })
        result = response[0]["generated_text"]
        return Response(result, status=200)
