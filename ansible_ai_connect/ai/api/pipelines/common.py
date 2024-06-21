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

from abc import abstractmethod
from typing import Generic, TypeVar


class PipelineElement:
    @abstractmethod
    def process(self, context) -> None:
        pass


T = TypeVar("T")
C = TypeVar("C")


class Pipeline(Generic[T, C]):
    def __init__(self, pipeline: list[PipelineElement], context: C):
        self.pipeline = pipeline
        self.context = context

    @abstractmethod
    def execute(self) -> T:
        pass
