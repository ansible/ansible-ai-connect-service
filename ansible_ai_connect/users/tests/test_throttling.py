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

from ansible_ai_connect.ai.api.views import Completions, Feedback
from ansible_ai_connect.test_utils import WisdomServiceAPITestCaseBaseOIDC

from ..throttling import GroupSpecificThrottle


class TestThrottling(WisdomServiceAPITestCaseBaseOIDC):
    def test_get_cache_key(self):
        class DummyRequest:
            def __init__(self, user):
                self.user = user

        throttling = GroupSpecificThrottle()
        request = DummyRequest(self.user)

        cache_key = throttling.get_cache_key(request, Completions())
        expected = f"throttle_user_{self.user.pk}_completions"
        self.assertEqual(expected, cache_key)

        cache_key = throttling.get_cache_key(request, Feedback())
        expected = f"throttle_user_{self.user.pk}_feedback"
        self.assertEqual(expected, cache_key)

    def test_format_rate(self):
        num_requests = 60

        rate = GroupSpecificThrottle.format_rate(num_requests, 1)
        self.assertEqual(rate, "60/second")
        rate = GroupSpecificThrottle.format_rate(num_requests, 60)
        self.assertEqual(rate, "60/minute")
        rate = GroupSpecificThrottle.format_rate(num_requests, 3600)
        self.assertEqual(rate, "60/hour")
        rate = GroupSpecificThrottle.format_rate(num_requests, 86400)
        self.assertEqual(rate, "60/day")

    def test_multiplier(self):
        throttling = GroupSpecificThrottle()

        user_rate_throttle = settings.COMPLETION_USER_RATE_THROTTLE

        view = Completions()
        multiplier = getattr(view, "throttle_cache_multiplier", None)
        self.assertIsNone(multiplier)
        rate = throttling.get_rate(view)
        self.assertEqual(rate, user_rate_throttle)

        view = Feedback()
        multiplier = getattr(view, "throttle_cache_multiplier", None)
        self.assertIsNotNone(multiplier)
        self.assertEqual(multiplier, 6.0)
        num_requests, duration = throttling.parse_rate(user_rate_throttle)
        expected = GroupSpecificThrottle.format_rate(int(num_requests * multiplier), duration)
        rate = throttling.get_rate(Feedback())
        self.assertEqual(rate, expected)
