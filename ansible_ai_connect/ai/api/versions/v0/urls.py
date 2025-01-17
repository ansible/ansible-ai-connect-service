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

from django.conf import settings
from django.urls import include, path

from .ai import urls as ai_urls
from .telemetry import urls as telemetry_urls
from .users import urls as me_urls
from .wca import urls as wca_urls

urlpatterns = [
    path("ai/", include(ai_urls)),
    path("me/", include(me_urls)),
]

if settings.DEBUG or settings.DEPLOYMENT_MODE == "saas":
    urlpatterns += [
        path("telemetry/", include(telemetry_urls)),
        path("wca/", include(wca_urls)),
    ]
