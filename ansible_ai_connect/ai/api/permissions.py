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

from django.apps import apps
from rest_framework import permissions

from ansible_ai_connect.ai.api.aws.wca_secret_manager import Suffixes


class IsOrganisationAdministrator(permissions.BasePermission):
    """
    Allow access only to users who are an administrator.
    """

    code = "permission_denied__user_not_org_administrator"
    message = "The User is not an Administrator of the Organization."

    def has_permission(self, request, view):
        user = request.user
        return user.rh_user_is_org_admin


class IsOrganisationLightspeedSubscriber(permissions.BasePermission):
    """
    Allow access only to users who have a Light Speed subscription.
    """

    code = "permission_denied__user_has_no_subscription"
    message = "The User does not have a subscription."

    def has_permission(self, request, view):
        user = request.user
        return user.rh_org_has_subscription


# See: https://issues.redhat.com/browse/AAP-18386
class BlockUserWithSeatButWCANotReady(permissions.BasePermission):
    """
    Block access to seated users if the WCA key was not set yet.
    """

    code = "permission_denied__org_not_ready_because_wca_not_configured"
    message = "The IBM watsonx Code Assistant model is not configured yet."

    def has_permission(self, request, view):
        user = request.user
        if user.organization is None:
            # We accept the Community users, the won't have access to WCA
            return True
        if user.rh_user_has_seat is not True:
            return True

        secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        org_has_api_key = secret_manager.secret_exists(user.organization.id, Suffixes.API_KEY)
        return org_has_api_key


# See: https://issues.redhat.com/browse/AAP-19427
class BlockUserWithoutSeat(permissions.BasePermission):
    """
    Block access to un-seated users when Tech Preview is finished
    """

    code = "permission_denied__user_with_no_seat"
    message = "User doesn't have access to the IBM watsonx Code Assistant."

    def has_permission(self, request, view):
        user = request.user

        return user.rh_user_has_seat


class IsAAPLicensed(permissions.BasePermission):
    """
    Block access to users when AAP license expired
    """

    code = "permission_denied__license_expired"
    message = "Ansible Automation Platform License has expired."

    def has_permission(self, request, view):
        return request.user.rh_aap_licensed
