import logging
from typing import TypedDict, Union
from uuid import UUID

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class APIPayload(BaseModel):
    model: str = ''
    prompt: str = ""
    context: str = ""
    userId: Union[UUID, None]
    suggestionId: Union[UUID, None]


class ModelMeshData(TypedDict):
    prompt: str
    context: str
    userId: Union[str, None]
    rh_user_has_seat: bool
    organization_id: Union[str, None]
    suggestionId: Union[str, None]


class ModelMeshPayload(BaseModel):
    instances: list[ModelMeshData]


class CodematchPostData(TypedDict):
    input: str
    rh_user_has_seat: bool
    organization_id: Union[str, None]
    suggestionId: Union[str, None]
