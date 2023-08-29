from ai.feature_flags import FeatureFlags, WisdomFlags
from django.conf import settings
from rest_framework import permissions

feature_flags = FeatureFlags()


class AcceptedTermsPermission(permissions.BasePermission):
    """
    Allow access only to users who have accepted terms and conditions.
    """

    def has_permission(self, request, view):
        user = request.user
        if user.is_authenticated:
            if user.commercial_terms_accepted or user.community_terms_accepted:
                return True
        return False


class IsOrganisationAdministrator(permissions.BasePermission):
    """
    Allow access only to users who are an administrator.
    """

    def has_permission(self, request, view):
        return True


class IsLightspeedSubscriber(permissions.BasePermission):
    """
    Allow access only to users who have a Light Speed subscripton.
    """

    def has_permission(self, request, view):
        return True


class IsWCAKeyApiFeatureFlagOn(permissions.BasePermission):
    """
    Allow access only to users allowed by feature flag
    """

    def has_permission(self, request, view):
        if settings.LAUNCHDARKLY_SDK_KEY:
            return feature_flags.get(WisdomFlags.WCA_KEY_API, request.user, "")
        return False


class IsWCAModelIdApiFeatureFlagOn(permissions.BasePermission):
    """
    Allow access only to users allowed by feature flag
    """

    def has_permission(self, request, view):
        if settings.LAUNCHDARKLY_SDK_KEY:
            return feature_flags.get(WisdomFlags.WCA_MODEL_ID_API, request.user, "")
        return False
