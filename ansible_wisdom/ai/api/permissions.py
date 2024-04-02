from django.apps import apps
from django.conf import settings
from rest_framework import permissions

from ansible_wisdom.ai.api.aws.wca_secret_manager import Suffixes


class AcceptedTermsPermission(permissions.BasePermission):
    """
    Allow access only to users who have accepted terms and conditions or paid users.
    """

    code = 'permission_denied__terms_of_use_not_accepted'
    message = "Terms of use have not been accepted."

    def has_permission(self, request, view):
        user = request.user
        if user.is_authenticated:
            if settings.ANSIBLE_AI_ENABLE_TECH_PREVIEW and user.community_terms_accepted:
                return True
            if user.rh_user_has_seat:
                return True
            if not settings.ANSIBLE_AI_ENABLE_TECH_PREVIEW:
                # The permission is deprecated and should be removed
                return True
        return False


class IsOrganisationAdministrator(permissions.BasePermission):
    """
    Allow access only to users who are an administrator.
    """

    code = 'permission_denied__user_not_org_administrator'
    message = "The User is not an Administrator of the Organization."

    def has_permission(self, request, view):
        user = request.user
        return user.rh_user_is_org_admin


class IsOrganisationLightspeedSubscriber(permissions.BasePermission):
    """
    Allow access only to users who have a Light Speed subscription.
    """

    code = 'permission_denied__user_has_no_subscription'
    message = "The User does not have a subscription."

    def has_permission(self, request, view):
        user = request.user
        return user.rh_org_has_subscription


# See: https://issues.redhat.com/browse/AAP-18386
class BlockUserWithoutSeatAndWCAReadyOrg(permissions.BasePermission):
    """
    Block access to seat-less user from of WCA-ready Commercial Org.
    """

    code = 'permission_denied__org_ready_user_has_no_seat'
    message = "Org's LightSpeed subscription is active but user has no seat."

    def has_permission(self, request, view):
        user = request.user
        if user.organization is None:
            # We accept the Community users, the won't have access to WCA
            return True
        if user.rh_user_has_seat is True:
            return True

        secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        org_has_api_key = secret_manager.secret_exists(user.organization.id, Suffixes.API_KEY)
        return not org_has_api_key


# See: https://issues.redhat.com/browse/AAP-18386
class BlockUserWithSeatButWCANotReady(permissions.BasePermission):
    """
    Block access to seated users if the WCA key was not set yet.
    """

    code = 'permission_denied__org_not_ready_because_wca_not_configured'
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

    code = 'permission_denied__user_with_no_seat'
    message = "User doesn't have access to the IBM watsonx Code Assistant."

    def has_permission(self, request, view):
        user = request.user
        if settings.ANSIBLE_AI_ENABLE_TECH_PREVIEW:
            return True

        return user.rh_user_has_seat


class BlockUserWithExpiredOnprem(permissions.BasePermission):
    """
    Block access to users when on prem license expired
    """

    code = 'permission_denied__license_expired'
    message = "Onprem License expired."

    def has_permission(self, request, view):
        return request.user.rh_aap_licensed
