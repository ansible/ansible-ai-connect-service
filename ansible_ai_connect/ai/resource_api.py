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

from ansible_base.resource_registry.registry import (
    ResourceConfig,
    ServiceAPIConfig,
    SharedResource,
)
from ansible_base.resource_registry.shared_types import UserType
from django.conf import settings
from django.contrib.auth import get_user_model


def get_service_type():
    service_type = "lightspeed"
    if not getattr(settings, "RESOURCE_SERVER", None):
        service_type = "aap"
    return service_type


class APIConfig(ServiceAPIConfig):
    service_type = get_service_type()


RESOURCE_LIST = [
    ResourceConfig(
        get_user_model(),
        shared_resource=SharedResource(serializer=UserType, is_provider=False),
        name_field="username",
    ),
]
