from rest_framework import permissions


class AcceptedTermsPermission(permissions.BasePermission):
    """
    Allow access only to users who have accepted terms and conditions.
    """

    def has_permission(self, request, view):
        user = request.user
        if user.is_authenticated:
            if user.date_terms_accepted:
                return True
        return False
