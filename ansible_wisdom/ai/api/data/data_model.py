import logging
from typing import List, TypedDict, Union
from uuid import UUID

from django.conf import settings
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class APIPayload(BaseModel):
    model_name: str = settings.ANSIBLE_AI_MODEL_NAME
    prompt: str = ""
    context: str = ""
    userId: Union[UUID, None]
    suggestionId: Union[UUID, None]


class ModelMeshData(TypedDict):
    prompt: str
    context: str


class ModelMeshPayload(BaseModel):
    instances: list[ModelMeshData]
