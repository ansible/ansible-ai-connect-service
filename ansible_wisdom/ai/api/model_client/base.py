#  Copyright Red Hat
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from abc import abstractmethod
from typing import Any, Dict, Optional

from django.conf import settings


class ModelMeshClient:
    def __init__(self, inference_url):
        self._inference_url = inference_url
        i = settings.ANSIBLE_AI_MODEL_MESH_API_TIMEOUT
        self._timeout = int(i) if i is not None else None

    @abstractmethod
    def infer(self, model_input, model_id: str = "", suggestion_id=None) -> Dict[str, Any]:
        pass

    def codematch(self, model_input, model_id):
        raise NotImplementedError

    def set_inference_url(self, inference_url):
        self._inference_url = inference_url

    def get_model_id(
        self,
        organization_id: Optional[int] = None,
        requested_model_id: str = '',
    ) -> str:
        return requested_model_id or settings.ANSIBLE_AI_MODEL_NAME

    def timeout(self, task_count=1):
        return self._timeout * task_count if self._timeout else None

    def get_chat_model(self, model_id):
        raise NotImplementedError
