from dataclasses import dataclass


@dataclass
class ModelTimeoutError(Exception):
    """The model server did not provide a prediction in the allotted time."""

    model_id: str = ''


@dataclass
class WcaException(Exception):
    """Base WCA Exception"""

    model_id: str = ''


@dataclass
class WcaBadRequest(WcaException):
    """Bad request to WCA"""


@dataclass
class WcaInvalidModelId(WcaException):
    """A WML instance is required for code generation.
    This is possibly caused by an invalid WCA Model ID being provided."""


@dataclass
class WcaKeyNotFound(WcaException):
    """WCA API Key was expected but not found."""


@dataclass
class WcaModelIdNotFound(WcaException):
    """WCA Model ID was expected but not found."""


@dataclass
class WcaEmptyResponse(WcaException):
    """WCA returned an empty response."""


@dataclass
class WcaTokenFailure(WcaException):
    """An attempt to retrieve a WCA Toke failed."""


@dataclass
class WcaInferenceFailure(WcaException):
    """An attempt to retrieve a WCA Toke failed."""


@dataclass
class WcaCodeMatchFailure(WcaException):
    """An attempt to retrieve a WCA Toke failed."""
