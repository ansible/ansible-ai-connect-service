import json
import logging
import sys
import boto3
import time
import json
import os
import sagemaker
from sagemaker.pytorch import PyTorchModel, PyTorchPredictor
from sagemaker.serializers import JSONSerializer
from sagemaker.deserializers import JSONDeserializer
import requests
from rest_framework.response import Response

from .base import ModelMeshClient

logger = logging.getLogger(__name__)

class AWSClient(ModelMeshClient):
    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)
        self.session = requests.Session()
        self.headers = {"Content-Type": "application/json"}

        endpoint_name = os.getenv("ANSIBLE_AI_MODEL_MESH_ENDPOINT", "project-wisdom-1679183323")

        #iam_client = boto3.client('iam')
        #self.role = iam_client.get_role(RoleName='AmazonSageMaker-ExecutionRole-20230314T201796')['Role']['Arn']
        sm_session = sagemaker.Session()

        self.predictor = PyTorchPredictor(
            endpoint_name=endpoint_name,
            sagemaker_session=sm_session,
            serializer=JSONSerializer(),
            deserializer=JSONDeserializer(),
        )

    def infer(self, model_input, model_name="wisdom") -> Response:
        input = model_input.get("instances", [{}])[0]
        result = self.predictor.predict(input)
        return Response(result, status=200)
