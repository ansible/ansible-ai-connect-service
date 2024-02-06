import logging
from typing import cast

from ai.api.aws.wca_secret_manager import Suffixes
from ai.apps import AiConfig
from django.apps import apps
from rest_framework import permissions
from users.models import User

logger = logging.getLogger(__name__)


class AcceptedTermsPermission(permissions.BasePermission):
    """
    Allow access only to users who have accepted terms and conditions or paid users.
    """

    def has_permission(self, request, view):
        user = cast(User, request.user)
        if user.is_authenticated:
            if user.community_terms_accepted or user.rh_user_has_seat:
                return True
        return False


class IsOrganisationAdministrator(permissions.BasePermission):
    """
    Allow access only to users who are an administrator.
    """

    def has_permission(self, request, view):
        user = cast(User, request.user)
        return user.rh_user_is_org_admin


class IsOrganisationLightspeedSubscriber(permissions.BasePermission):
    """
    Allow access only to users who have a Light Speed subscription.
    """

    def has_permission(self, request, view):
        user = cast(User, request.user)
        return user.rh_org_has_subscription


# See: https://issues.redhat.com/browse/AAP-18386
class BlockUserWithoutSeatAndWCAReadyOrg(permissions.BasePermission):
    """
    Block access to seat-less user from of WCA-ready Commercial Org.
    """

    code = 'permission_denied__org_ready_user_has_no_seat'
    message = "Org's LightSpeed subscription is active but user has no seat."

    def has_permission(self, request, view):
        user = cast(User, request.user)
        if user.organization is None:
            # We accept the Community users, the won't have access to WCA
            return True
        if user.rh_user_has_seat is True:
            return True

        ai_config = cast(AiConfig, apps.get_app_config("ai"))
        secret_manager = ai_config.get_wca_secret_manager()
        if not secret_manager:
            logger.error("Error accessing the secret manager")
            return False

        org_has_api_key = secret_manager.secret_exists(user.organization.id, Suffixes.API_KEY)
        return not org_has_api_key


# See: https://issues.redhat.com/browse/AAP-18386
class BlockUserWithSeatButWCANotReady(permissions.BasePermission):
    """
    Block access to seated users if the WCA key was not set yet.
    """

    code = 'permission_denied__org_not_ready_because_wca_not_configured'
    message = "The IBM watsonx Code Assistant model is not configured yet."

    def has_permission(self, request, view) -> bool:
        user = cast(User, request.user)
        if user.organization is None:
            # We accept the Community users, the won't have access to WCA
            return True
        if user.rh_user_has_seat is not True:
            return True

        ai_config = cast(AiConfig, apps.get_app_config("ai"))
        secret_manager = ai_config.get_wca_secret_manager()
        if not secret_manager:
            logger.error("Error accessing the secret manager")
            return False

        org_has_api_key = secret_manager.secret_exists(user.organization.id, Suffixes.API_KEY)
        return org_has_api_key
