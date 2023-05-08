from django.conf import settings
from rest_framework.throttling import BaseThrottle, UserRateThrottle


class GroupSpecificThrottle(UserRateThrottle):
    """
    Allows using settings.SPECIAL_THROTTLING_GROUPS to specify Django user Group
    names that have a special meaning and correspond to a scope under the
    settings.REST_FRAMEWORK['DEFAULT_THROTTLING_RATES'] setting,
    e.g. performance testing users get a different throttle rate than everyone
    else.
    """

    GROUPS = settings.SPECIAL_THROTTLING_GROUPS

    def __init__(self):
        # Override, since we can't decide what the scope and rate are
        # until we see the request.
        pass

    def get_scope(self, request, view):
        user_groups = set(request.user.groups.values_list('name', flat=True))
        return next((group for group in self.GROUPS if group in user_groups), 'user')

    def allow_request(self, request, view):
        # Allow the normal UserRateThrottle scope ('user') to be overridden if
        # the user is a member of one of our special groups.
        self.scope = self.get_scope(request, view)

        # get_rate() will now pull the rate setting based on our dynamically set
        # scope value.
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)

        return super().allow_request(request, view)
