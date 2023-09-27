from dataclasses import dataclass


@dataclass
class ModelTimeoutError(Exception):
    """The model server did not provide a prediction in the allotted time."""

    model_id: str = ''
