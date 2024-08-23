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

import uuid
from dataclasses import dataclass


@dataclass
class ModelTimeoutError(Exception):
    """The model server did not provide a prediction in the allotted time."""

    model_id: str = ""


@dataclass
class WcaException(Exception):
    """Base WCA Exception"""

    model_id: str = ""
    json_response: dict = None


@dataclass
class WcaBadRequest(WcaException):
    """Bad request to WCA"""


@dataclass
class WcaUsernameNotFound(WcaException):
    """WCA Username was expected but not found."""


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
class WcaNoDefaultModelId(WcaException):
    """No default WCA Model ID was found."""


@dataclass
class WcaEmptyResponse(WcaException):
    """WCA returned an empty response."""


@dataclass
class WcaTokenFailure(WcaException):
    """An attempt to retrieve a WCA Token failed."""


@dataclass
class WcaTokenFailureApiKeyError(WcaException):
    """An attempt to retrieve a WCA Token failed due to a problem with the provided API Key."""


@dataclass
class WcaCloudflareRejection(WcaException):
    """Cloudflare rejected the request."""


@dataclass
class WcaHAPFilterRejection(WcaException):
    """WCA Hate, Abuse, and Profanity filter rejection."""


@dataclass
class WcaUserTrialExpired(WcaException):
    """WCA notifies that user's trial has expired."""


@dataclass
class WcaInferenceFailure(WcaException):
    """An attempt to run a WCA inference failed."""


@dataclass
class WcaCodeMatchFailure(WcaException):
    """An attempt to run a WCA code match failed."""


@dataclass
class WcaRequestIdCorrelationFailure(WcaException):
    """WCA Request/Response X-Request-ID correlation failed."""

    def __init__(self, model_id, x_request_id: uuid.uuid4):
        super().__init__(model_id)
        self.x_request_id: uuid.uuid4 = x_request_id


@dataclass
class WcaInstanceDeleted(WcaException):
    """WCA Instance associated with the Model ID has been deleted."""
