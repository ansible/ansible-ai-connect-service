#  Copyright Red Hat
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from django.conf import settings
from rest_framework.throttling import UserRateThrottle


class GroupSpecificThrottle(UserRateThrottle):
    """
    Allows using settings.SPECIAL_THROTTLING_GROUPS to specify Django user Group
    names that have a special meaning and correspond to a scope under the
    settings.REST_FRAMEWORK['DEFAULT_THROTTLING_RATES'] setting,
    e.g. performance testing users get a different throttle rate than everyone
    else.
    """

    GROUPS = settings.SPECIAL_THROTTLING_GROUPS

    # The attribute name that may be defined in views to add a suffix to cache keys
    cache_key_suffix_attr = "throttle_cache_key_suffix"

    # The attribute name that may be definied in views to give a larger (or smaller) rate limit
    cache_key_multipiler_attr = "throttle_cache_multiplier"

    def __init__(self):
        # Override, since we can't decide what the scope and rate are
        # until we see the request.
        pass

    def get_scope(self, request, view):
        user_groups = set(request.user.groups.values_list("name", flat=True))
        return next((group for group in self.GROUPS if group in user_groups), "user")

    def allow_request(self, request, view):
        # Allow the normal UserRateThrottle scope ('user') to be overridden if
        # the user is a member of one of our special groups.
        self.scope = self.get_scope(request, view)

        # get_rate() will now pull the rate setting based on our dynamically set
        # scope value.
        self.rate = self.get_rate(view)
        self.num_requests, self.duration = self.parse_rate(self.rate)

        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        cache_key = super().get_cache_key(request, view)
        # If a cache key suffix is defined in the view, append it to the key
        cache_key_suffix = getattr(view, self.cache_key_suffix_attr, None)
        if cache_key_suffix:
            cache_key += cache_key_suffix
        return cache_key

    def get_rate(self, view):
        rate = super().get_rate()

        multipiler = getattr(view, self.cache_key_multipiler_attr, None)
        # If a multiplier is defined in the view, modify the rate based on it
        if multipiler:
            num_requests, duration = self.parse_rate(rate)
            rate = GroupSpecificThrottle.format_rate(
                int(float(multipiler) * num_requests), duration
            )
        return rate

    @staticmethod
    def format_rate(num_requests, duration):
        duration_unit = {
            1: "second",
            60: "minute",
            3600: "hour",
            86400: "day",
        }[duration]
        return f"{num_requests}/{duration_unit}"


class EndpointRateThrottle(GroupSpecificThrottle):
    """
    Rate limit on the total number of calls from authenticated users. For test
    and unauthenticated users, this works in the same way as its base class,
    GroupSpecificThrottle
    """

    def get_scope(self, request, view):
        scope = super().get_scope(request, view)
        return scope if scope != "user" else self.scope

    def get_cache_key(self, request, view):
        # For test and unauthenticated users, return the same cache key as
        # the one GroupSpecificThrottle provides.
        scope = super().get_scope(request, view)
        if scope != "user" or not request.user.is_authenticated:
            return super().get_cache_key(request, view)

        # Return the same cache key for all authenticated users.
        ident = "user"
        return self.cache_format % {"scope": self.scope, "ident": ident}
