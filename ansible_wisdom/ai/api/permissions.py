from django.apps import apps
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


class CustomerWithASeatPermission(permissions.BasePermission):
    """
    Allow access to Red Hat SSO if they are entitled to a seat.
    """

    def has_permission(self, request, view):
        user = request.user
        # TODO:
        #  - do we accept community users with Red Hat SSO access
        #  - do we have different 'view' depending on the kind of users?
        if not user.social_auth.values():
            return True
        if user.social_auth.values()[0]["provider"] != "oidc":
            return True
        is_commercial = user.groups.filter(name='Commercial').exists()
        if not is_commercial:
            return True
        ciam_checker = apps.get_app_config("ai").get_ciam_checker()
        uid = user.social_auth.values()[0]["uid"]
        organization_id = user.organization_id
        return ciam_checker.check(uid, organization_id)
