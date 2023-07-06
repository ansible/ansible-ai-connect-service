from ai.api.tests.test_views import WisdomServiceAPITestCaseBase
from ai.api.views import Attributions, Completions, Feedback

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
