import logging
from typing import List, Union

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Payload(BaseModel):
    model: Union[str, None]
    prompt: str = ""
    context: str = ""
    temperature: Union[int, None]
    max_tokens: Union[int, None]
    top_p: Union[int, None]
    frequency_penalty: Union[int, None]
    presence_penalty: Union[int, None]


class ResultItem(BaseModel):
    text: str


class Result(BaseModel):
    choices: List[ResultItem]
