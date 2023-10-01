from dataclasses import dataclass
from typing import Union

from ai.api.data.data_model import APIPayload
from rest_framework.request import Request
from rest_framework.response import Response


@dataclass
class CompletionContext:
    request: Request
    response: Response = None

    payload: APIPayload = None
    model_id: str = ""
    original_indent: int = 0

    predictions: dict[str, Union[list[str], str]] = None
    ano_predictions: dict[str, Union[list[str], str]] = None
    postprocessd_predictions: dict[str, Union[list[str], str]] = None
    task_results: list[dict[str, str]] = None
