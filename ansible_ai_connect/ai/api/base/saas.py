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

from ansible_ai_connect.ai.api import exceptions


class APIViewSaasMixin:

    def initial(self, request, *args, **kwargs):
        self.check_saas_settings(request)
        return super().initial(request, *args, **kwargs)

    def check_saas_settings(self, request):
        """Call the correct error function when DEPLOYMENT_MODE is not saas
        and not in DEBUG mode"""
        if not settings.DEBUG and settings.DEPLOYMENT_MODE != "saas":
            self.not_implemented_error(
                request, message="This functionality is not available in the current environment"
            )

    def not_implemented_error(self, request, message=None, code=None):
        """
        Raise not implement exception when called
        """
        raise exceptions.NotImplementedException(detail=message, code=code)
