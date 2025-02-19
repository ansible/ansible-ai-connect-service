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
from ansible_base.resource_registry.urls import urlpatterns as resource_api_urls
from django.urls import include, path

from .versions.v0 import urls as v0_urls
from .versions.v1 import urls as v1_urls

urlpatterns = [
    path("v0/", include((v0_urls, "ai"), namespace="v0")),
    path("v1/", include((v1_urls, "ai"), namespace="v1")),
    path("v1/", include(resource_api_urls)),
]
