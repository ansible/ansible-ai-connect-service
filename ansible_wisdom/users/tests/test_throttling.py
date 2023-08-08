from ai.api.tests.test_views import WisdomServiceAPITestCaseBase
from ai.api.views import Attributions, Completions, Feedback
from django.conf import settings

from ..throttling import GroupSpecificThrottle


class TestThrottling(WisdomServiceAPITestCaseBase):
    def test_get_cache_key(self):
        class DummyRequest:
            def __init__(self, user):
                self.user = user

        throttling = GroupSpecificThrottle()
        request = DummyRequest(self.user)

        cache_key = throttling.get_cache_key(request, Completions())
        expected = f'throttle_user_{self.user.pk}_completions'
        self.assertEqual(expected, cache_key)

        cache_key = throttling.get_cache_key(request, Attributions())
        expected = f'throttle_user_{self.user.pk}_attributions'
        self.assertEqual(expected, cache_key)

        cache_key = throttling.get_cache_key(request, Feedback())
        expected = f'throttle_user_{self.user.pk}_feedback'
        self.assertEqual(expected, cache_key)

    def test_format_rate(self):
        num_requests = 60

        rate = GroupSpecificThrottle.format_rate(num_requests, 1)
        self.assertEqual(rate, '60/second')
        rate = GroupSpecificThrottle.format_rate(num_requests, 60)
        self.assertEqual(rate, '60/minute')
        rate = GroupSpecificThrottle.format_rate(num_requests, 3600)
        self.assertEqual(rate, '60/hour')
        rate = GroupSpecificThrottle.format_rate(num_requests, 86400)
        self.assertEqual(rate, '60/day')

    def test_multiplier(self):
        throttling = GroupSpecificThrottle()

        user_rate_throttle = settings.COMPLETION_USER_RATE_THROTTLE

        view = Completions()
        multiplier = getattr(view, 'throttle_cache_multiplier', None)
        self.assertIsNone(multiplier)
        rate = throttling.get_rate(view)
        self.assertEqual(rate, user_rate_throttle)

        view = Feedback()
        multiplier = getattr(view, 'throttle_cache_multiplier', None)
        self.assertIsNotNone(multiplier)
        self.assertEqual(multiplier, 6.0)
        num_requests, duration = throttling.parse_rate(user_rate_throttle)
        expected = GroupSpecificThrottle.format_rate(int(num_requests * multiplier), duration)
        rate = throttling.get_rate(Feedback())
        self.assertEqual(rate, expected)
