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
from rest_framework.permissions import BasePermission


class IsRHInternalUser(BasePermission):
    """
    Allow access only to users who are Red Hat internal users.
    """

    code = "permission_denied__user_not_rh_internal"
    message = "The User is not a Red Hat employee."

    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and user.rh_internal


class IsTestUser(BasePermission):
    """
    Allow access only to test users, who are found in the "test" Django group
    """

    code = "permission_denied_user_not_test_user"
    message = "The user is not a Test User"

    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and user.groups.filter(name="test").exists()


class IsAAPUser(BasePermission):
    """
    Allow access only to authenticated AAP users
    """

    code = "permission_denied_user_not_from_aap"
    message = "The user is not an AAP User"

    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and user.aap_user
