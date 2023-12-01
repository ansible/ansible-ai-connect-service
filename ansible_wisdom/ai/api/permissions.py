from ai.api.aws.wca_secret_manager import Suffixes
from django.apps import apps
from rest_framework import permissions


class AcceptedTermsPermission(permissions.BasePermission):
    """
    Allow access only to users who have accepted terms and conditions or paid users.
    """

    def has_permission(self, request, view):
        user = request.user
        if user.is_authenticated:
            if user.community_terms_accepted or user.rh_user_has_seat:
                return True
        return False


class IsOrganisationAdministrator(permissions.BasePermission):
    """
    Allow access only to users who are an administrator.
    """

    def has_permission(self, request, view):
        user = request.user
        return user.rh_user_is_org_admin


class IsOrganisationLightspeedSubscriber(permissions.BasePermission):
    """
    Allow access only to users who have a Light Speed subscription.
    """

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
        if user.organization_id is None:
            # We accept the Community users, the won't have access to WCA
            return True
        if user.rh_user_has_seat is True:
            return True
        secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        org_has_api_key = secret_manager.secret_exists(user.organization_id, Suffixes.API_KEY)
        return not org_has_api_key
