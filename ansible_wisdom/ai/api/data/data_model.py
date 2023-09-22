import logging
from enum import Enum
from typing import Any, TypedDict, Union
from uuid import UUID

from pydantic import BaseModel

from ansible_wisdom.ai.api.serializers import DataSource

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


class AttributionData(BaseModel):
    repo_name: str = ''
    repo_url: str = ""
    path: str = ""
    license: str = ""
    score: float = 0
    data_source_description: str = ""
    data_source: Enum = ""
    ansible_type = -1

    def __init__(self, **data: Any):
        super().__init__(**data)
        self.data_source = DataSource[self.data_source_description.replace("-", "_").upper()]


class AttributionDataTransformer(BaseModel):
    code_matches: list[AttributionData]

    def attributions(self):
        return self.dict().get("code_matches", "")
