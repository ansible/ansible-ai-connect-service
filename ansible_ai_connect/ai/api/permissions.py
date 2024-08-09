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
from rest_framework import permissions

CONTINUE = True
BLOCK = False


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


class BlockWCANotReadyButTrialAvailable(permissions.BasePermission):
    """
    WCA is not ready but the user can apply for the Trial period
    """

    code = "permission_denied__can_apply_for_trial"
    message = "Access denied but user can apply for a trial period."

    def has_permission(self, request, view):
        user = request.user
        if not settings.ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL:
            return CONTINUE

        if not request.user.organization:
            return CONTINUE

        # accept user with active Trial period
        if any(up.is_active for up in request.user.userplan_set.all()):
            return CONTINUE

        org_has_api_key = user.organization.has_api_key
        return CONTINUE if org_has_api_key else BLOCK


# See: https://issues.redhat.com/browse/AAP-18386
class BlockUserWithoutSeatAndWCAReadyOrg(permissions.BasePermission):
    """
    Block access to seat-less user from of WCA-ready Commercial Org.
    """

    code = "permission_denied__org_ready_user_has_no_seat"
    message = (
        f"Org's {settings.ANSIBLE_AI_PROJECT_NAME} subscription is active but user has no seat."
    )

    def has_permission(self, request, view):
        user = request.user
        if user.organization is None:
            # We accept the Community users, the won't have access to WCA
            return CONTINUE
        if user.rh_user_has_seat is True:
            return CONTINUE

        # accept user with active Trial period
        if any(up.is_active for up in request.user.userplan_set.all()):
            return CONTINUE

        org_has_api_key = user.organization.has_api_key

        return BLOCK if org_has_api_key else CONTINUE


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
            return CONTINUE
        if user.rh_user_has_seat is not True:
            return CONTINUE

        # If the user has an active Trial, we continue
        if any(up.is_active for up in request.user.userplan_set.all()):
            return CONTINUE

        org_has_api_key = user.organization.has_api_key
        return CONTINUE if org_has_api_key else BLOCK


# See: https://issues.redhat.com/browse/AAP-19427
class BlockUserWithoutSeat(permissions.BasePermission):
    """
    Block access to un-seated users when Tech Preview is finished
    """

    code = "permission_denied__user_with_no_seat"
    message = "User doesn't have access to the IBM watsonx Code Assistant."

    def has_permission(self, request, view):
        user = request.user
        if settings.ANSIBLE_AI_ENABLE_TECH_PREVIEW:
            return CONTINUE

        # If the user has an active Trial, we continue
        if any(up.is_active for up in request.user.userplan_set.all()):
            return CONTINUE

        return CONTINUE if user.rh_user_has_seat else BLOCK


class IsAAPLicensed(permissions.BasePermission):
    """
    Block access to users when AAP license expired
    """

    code = "permission_denied__license_expired"
    message = "Ansible Automation Platform License has expired."

    def has_permission(self, request, view):
        return CONTINUE if request.user.rh_aap_licensed else BLOCK
