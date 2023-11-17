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
