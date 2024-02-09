from dataclasses import dataclass, field
from typing import Any, Union

from rest_framework.request import Request
from rest_framework.response import Response

from ansible_wisdom.ai.api.data.data_model import APIPayload


@dataclass
class CompletionContext:
    request: Request
    response: Response = None

    metadata: dict[str, Any] = field(default_factory=dict)

    model_id: str = ""
    payload: APIPayload = None
    original_indent: int = 0

    predictions: dict[str, Union[list[str], str]] = field(default_factory=dict)
    anonymized_predictions: dict[str, Union[list[str], str]] = field(default_factory=dict)
    post_processed_predictions: dict[str, Union[list[str], str]] = field(default_factory=dict)

    task_results: list[dict[str, str]] = field(default_factory=list)
