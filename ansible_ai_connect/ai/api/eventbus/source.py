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
#  limitations

from enum import StrEnum

from ansible_ai_connect.ai.api.eventbus.sinks import chat_service


class EventType(StrEnum):
    CHAT = "chat"


class EventBus:

    def send(self, event_type: EventType, **kwargs) -> any:
        data = None
        match event_type:
            case "chat":
                response = chat_service.send(
                    event_type,
                    conversation_id=kwargs["conversation_id"],
                    req_query=kwargs["query"],
                    req_system_prompt=kwargs["system_prompt"],
                    req_model_id=kwargs["model_id"],
                    req_provider=kwargs["provider"],
                )
                data = response[0][1]
        return data
