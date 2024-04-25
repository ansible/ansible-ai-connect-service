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
