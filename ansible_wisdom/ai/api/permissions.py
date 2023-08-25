from rest_framework import permissions


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
