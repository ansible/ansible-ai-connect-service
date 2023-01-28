import logging
from typing import List, TypedDict, Union

from django.conf import settings
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class APIPayload(BaseModel):
    model_name: str = settings.ANSIBLE_AI_MODEL_NAME
    prompt: str = ""
    context: str = ""
    temperature: Union[int, None]
    max_tokens: Union[int, None]
    top_p: Union[int, None]
    frequency_penalty: Union[int, None]
    presence_penalty: Union[int, None]
    user_id: Union[str, None]
    suggestion_id: Union[str, None]


class ModelMeshData(TypedDict):
    prompt: str
    context: str


class ModelMeshPayload(BaseModel):
    instances: list[ModelMeshData]
