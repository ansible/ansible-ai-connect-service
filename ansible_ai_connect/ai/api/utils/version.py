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
from django.urls import reverse


def get_api_version_view_name(view_name: str, api_version: str | None = None) -> str:
    """
    Get the view name with version, if no version supplied, use REST FRAMEWORK
    default configured version
    :param view_name: the registered view
    :param api_version: the version requested the view name is registered
    :return: view name of the version
    """
    if not api_version:
        api_version = getattr(settings, "REST_FRAMEWORK", {}).get("DEFAULT_VERSION")
    if api_version:
        view_name = f"{api_version}:{view_name}"
    return view_name


def api_version_reverse(view_name: str, api_version: str | None = None, **kwargs) -> str:
    """
    Return the django reverse of a versioned view name
    :param view_name: the registered view
    :param api_version: the version requested the view name is registered
    :param kwargs: other django reverse kwargs
    """
    return reverse(get_api_version_view_name(view_name, api_version=api_version), **kwargs)
