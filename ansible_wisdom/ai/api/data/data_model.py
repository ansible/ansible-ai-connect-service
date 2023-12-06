import logging
from abc import abstractmethod
from typing import Any, TypedDict, Union
from uuid import UUID

from ai.api.serializers import DataSource
from pydantic import BaseModel, validator

logger = logging.getLogger(__name__)


class APIPayload(BaseModel):
    model: str = ''
    prompt: str = ""
    original_prompt: str = ""
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
    data_source = -1

    def __init__(self, **data: Any):
        super().__init__(**data)
        if not self.data_source_description:
            self.data_source_description = DataSource(self.data_source).label


class BaseContentMatchResponseDto(BaseModel):
    meta: dict

    @abstractmethod
    def data(self) -> dict:
        pass

    @property
    def content_matches(self):
        return {"contentmatch": self.data()}

    @property
    def encode_duration(self):
        return self.meta.get("encode_duration", "")

    @property
    def search_duration(self):
        return self.meta.get("search_duration", "")


class ContentMatchResponseDto(BaseContentMatchResponseDto):
    code_matches: list[ContentMatchResponseData]

    @validator('code_matches')
    @classmethod
    def trim_to_first_three(cls, items):
        return items[:3]

    def data(self):
        return self.dict()["code_matches"]


class AttributionsResponseDto(BaseContentMatchResponseDto):
    attributions: list[ContentMatchResponseData]

    def data(self):
        return self.dict()["attributions"]
