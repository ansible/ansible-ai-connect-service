# Create your views here.
import logging

from django.apps import apps
from rest_framework.response import Response
from rest_framework.views import APIView
from .filter_predictions import scan_str_content, get_secret
from .data.data_model import APIPayload, ModelMeshPayload
import re
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)
import q

class Completions(APIView):
    def post(self, request) -> Response:
        model_mesh_client = apps.get_app_config("ai").model_mesh_client
        payload = APIPayload(**request.data)
        model_name = payload.model_name
        model_mesh_payload = ModelMeshPayload(
            instances=[{"prompt": payload.prompt, "context": payload.context}]
        )
        data = model_mesh_payload.dict()
        logger.debug(f"Input to inference: {data}")
        response = model_mesh_client.infer(data, model_name=model_name)
        output_data = response.data
        q(output_data['predictions'])
        temp_predictions = []
        for each in output_data['predictions']:
            q(each)
            value = scan_str_content(each, '.txt')
            q(value)
            if value:
                for every in value:
                    secret_val = get_secret(every)
                    new_content = re.sub(secret_val, "{{ }}", each)
                    each = new_content
                #each = new_content
                q(each)
            temp_predictions.append(each)
        #new_content = file.read()
        output_data['predictions'] = temp_predictions
        logger.debug(f"Response from inference: {response.data}")
        q(response)
        return response
