import logging
from enum import Enum
from typing import Any, TypedDict, Union
from uuid import UUID

from ai.api.serializers import DataSource
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


class ContentMatchPayloadData(TypedDict):
    suggestions: list[str]
    user_id: Union[str, None]
    rh_user_has_seat: bool
    organization_id: Union[str, None]
    suggestionId: Union[str, None]


class ContentMatchResponseData(BaseModel):
    repo_name: str = ''
    repo_url: str = ""
    path: str = ""
    license: str = ""
    score: float = 0
    data_source_description: str = ""
    data_source: Enum = DataSource.UNKNOWN
    ansible_type = -1

    def __init__(self, **data: Any):
        super().__init__(**data)
        self.data_source = DataSource[self.data_source_description.replace("-", "_").upper()]


class ContentMatchResponseDto(BaseModel):
    code_matches: list[ContentMatchResponseData]
    meta: dict

    @property
    def encode_duration(self):
        return self.meta.get("encode_duration", "")

    @property
    def search_duration(self):
        return self.meta.get("search_duration", "")

    @property
    def content_matches(self):
        return {"contentmatch": self.dict()["code_matches"]}
