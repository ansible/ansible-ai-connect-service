import logging

import requests

from ..exceptions import ModelTimeoutError
from . import WCAClient

logger = logging.getLogger(__name__)


class WCACodegenClient(WCAClient):
    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)
        # path matches ANSIBLE_WCA_INFERENCE_URL="https://api.dataplatform.test.cloud.ibm.com"
        self._prediction_url = f"{self._inference_url}/v1/wca/codegen/ansible"

    def infer(self, model_input, model_name=None):
        logger.debug(f"Input prompt: {model_input}")
        prompt = model_input.get("instances", [{}])[0].get("prompt", "")
        context = model_input.get("instances", [{}])[0].get("context", "")
        rh_user_has_seat = model_input.get("instances", [{}])[0].get("rh_user_has_seat", False)
        organization_id = model_input.get("instances", [{}])[0].get("organization_id", None)

        if prompt.endswith('\n') is False:
            prompt = f"{prompt}\n"

        model_id = self.get_model_id(rh_user_has_seat, organization_id, model_name)
        data = {
            "model_id": model_id,
            "prompt": f"{context}{prompt}",
        }

        logger.debug(f"Inference API request payload: {data}")

        try:
            # TODO: store token and only fetch a new one if it has expired
            api_key = self.get_api_key(rh_user_has_seat, organization_id)
            token = self.get_token(api_key)
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token['access_token']}",
            }

            result = self.session.post(
                self._prediction_url, headers=headers, json=data, timeout=self.timeout
            )
            result.raise_for_status()
            response = result.json()
            response['model_id'] = model_id
            logger.debug(f"Inference API response: {response}")
            return response
        except requests.exceptions.ReadTimeout:
            raise ModelTimeoutError
