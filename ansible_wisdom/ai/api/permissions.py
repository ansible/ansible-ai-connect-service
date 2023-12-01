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
class IsOrganisationLightspeedSubscriberFullySetup(permissions.BasePermission):
    """
    Allow access only to RH  to users who have a Light Speed subscription
    and an API key
    """

    code = 'permission_denied_wca_api_key_is_missing'
    message = "LightSpeed subscription is active but API key is not set yet."

    def has_permission(self, request, view):
        user = request.user
        if user.organization_id is False:
            # We accept the Community users, the won't have access to WCA
            return True
        secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        org_has_api_key = secret_manager.secret_exists(user.organization_id, Suffixes.API_KEY)
        return org_has_api_key
