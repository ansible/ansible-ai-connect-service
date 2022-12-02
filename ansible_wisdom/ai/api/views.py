# Create your views here.
import logging

from django.apps import apps
from rest_framework.response import Response
from rest_framework.views import APIView

from .data.data_model import Payload, Result, ResultItem
from .utils.request import openai_to_wisdom

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)


class Completions(APIView):
    def post(self, request):
        payload = Payload(**request.data)

        print("---payload----", payload)
        # TODO: remove after we start using wisdom sdk on the client side
        model = apps.get_app_config('ai').model
        prompt_type = ""
        if not payload.context:
            # In case openai request, the `context` key is absent and the
            # `prompt` is the content of ansible file till last line (natural language).
            payload, prompt_type = openai_to_wisdom(payload)

            logger.debug(f"identified prompt: {payload.prompt}")
            logger.debug(f"identified context: {payload.context}")

        if prompt_type == "empty":
            text = ""
        elif prompt_type == "comment" or prompt_type == "generic":
            result = model.evaluate(payload)
            result_split = result.split('\n', 1)
            # add prompt into results
            text = payload.prompt + '\n' + result_split[1].rstrip().rstrip('\n') + '\n'
        else:  # prompt_type == "task-name"
            result = model.evaluate(payload)
            result_split = result.split('\n', 1)
            text = result_split[1].rstrip().rstrip('\n') + '\n'

        item = ResultItem(text=text)
        response = Result(choices=[item])
        logger.debug(f"Response: {response}")
        return Response(response.dict())
