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

from django.apps import apps
from django.dispatch import Signal, receiver

from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    ChatBotParameters,
    ModelPipelineChatBot,
)

chat_service = Signal()


@receiver(chat_service)
def chat_service_receiver(
    sender, conversation_id, req_query, req_system_prompt, req_model_id, req_provider, **kwargs
):
    llm: ModelPipelineChatBot = apps.get_app_config("ai").get_model_pipeline(ModelPipelineChatBot)
    data = llm.invoke(
        ChatBotParameters.init(
            query=req_query,
            system_prompt=req_system_prompt,
            model_id=req_model_id or llm.config.model_id,
            provider=req_provider,
            conversation_id=conversation_id,
        )
    )
    return data
