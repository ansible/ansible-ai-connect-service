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

import logging

from langchain_community.llms import Ollama

from .langchain import LangChainClient

logger = logging.getLogger(__name__)


# NOTE Heavily inspired by bam_client.py and we should ultimately merge the
# two drivers to create a generic one.
class OllamaClient(LangChainClient):
    def get_chat_model(self, model_id):
        return Ollama(
            base_url=self._inference_url,
            model=model_id,
        )
