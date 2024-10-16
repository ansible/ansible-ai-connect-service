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
from rest_framework.permissions import IsAuthenticated


class IsAuthenticatedRHEmployee(IsAuthenticated):
    """
    Allow access only to users who are authenticated Red Hat employees.
    """

    code = "permission_denied__user_not_authenticated_rh_employee"
    message = "The User is not an authenticated Red Hat employee."

    def has_permission(self, request, view):
        permitted = super().has_permission(request, view)
        if not permitted:
            return permitted

        user = request.user
        return user.rh_employee
