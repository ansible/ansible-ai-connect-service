from ai.api.tests.test_views import WisdomServiceAPITestCaseBase
from ai.api.views import Completions

from ..throttling import GroupSpecificThrottle


class TestThrottling(WisdomServiceAPITestCaseBase):
    def test_get_cache_key(self):
        class DummyRequest:
            def __init__(self, user, method, path):
                self.user = user
                self.method = method
                self.path = path

        throttling = GroupSpecificThrottle()
        method = 'POST'
        path = '/api/v0/ai/completions/'
        request = DummyRequest(self.user, method, path)
        view = Completions()

        cache_key = throttling.get_cache_key(request, view)
        expected = f'throttle_user_{self.user.pk}_{method}_{path}'
        self.assertIsNotNone(expected, cache_key)
