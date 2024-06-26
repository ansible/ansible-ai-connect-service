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
from abc import abstractmethod
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, validator
from typing_extensions import TypedDict

from ansible_ai_connect.ai.api.serializers import DataSource

logger = logging.getLogger(__name__)


class APIPayload(BaseModel):
    model: str = ""
    prompt: str = ""
    original_prompt: str = ""
    context: str = ""
    userId: Optional[UUID] = None
    suggestionId: Optional[UUID] = None


class ModelMeshData(TypedDict):
    prompt: str
    context: str
    suggestionId: Optional[str] = None


class ModelMeshPayload(BaseModel):
    instances: list[ModelMeshData]


class ContentMatchPayloadData(TypedDict):
    suggestions: list[str]
    user_id: Optional[str]
    rh_user_has_seat: bool
    organization_id: Optional[int] = None
    suggestionId: Optional[str] = None


class ContentMatchResponseData(BaseModel):
    repo_name: str = ""
    repo_url: str = ""
    path: str = ""
    license: str = ""
    score: float = 0
    data_source_description: str = ""
    data_source: int = -1

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

    @validator("code_matches")
    @classmethod
    def trim_to_first_three(cls, items):
        return items[:3]

    def data(self):
        return self.dict()["code_matches"]
