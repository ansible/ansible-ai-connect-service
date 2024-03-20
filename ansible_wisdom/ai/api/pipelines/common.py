from abc import abstractmethod
from typing import Generic, TypeVar


class PipelineElement:
    @abstractmethod
    def process(self, context) -> None:
        pass


T = TypeVar('T')
C = TypeVar('C')


class Pipeline(Generic[T, C]):
    def __init__(self, pipeline: list[PipelineElement], context: C):
        self.pipeline = pipeline
        self.context = context

    @abstractmethod
    def execute(self) -> T:
        pass
