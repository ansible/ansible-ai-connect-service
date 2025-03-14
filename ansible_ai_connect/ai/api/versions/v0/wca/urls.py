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

from django.urls import path

from . import views

urlpatterns = [
    path("apikey/", views.WCAApiKeyView.as_view(), name="wca_api_key"),
    path("modelid/", views.WCAModelIdView.as_view(), name="wca_model_id"),
    path("apikey/test/", views.WCAApiKeyValidatorView.as_view(), name="wca_api_key_validator"),
    path("modelid/test/", views.WCAModelIdValidatorView.as_view(), name="wca_model_id_validator"),
]
