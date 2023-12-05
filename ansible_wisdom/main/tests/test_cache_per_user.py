import time
from unittest.mock import Mock

from django.test import TestCase
from django.utils.decorators import method_decorator
from django.views.generic.base import View
from main.cache.cache_per_user import cache_per_user
from rest_framework.request import HttpRequest, Request
from rest_framework.response import Response


class TestCachePerUser(TestCase):
    class TestResponse(Response):
        @property
        def rendered_content(self):
            return f"timestamp={time.time()}"

    class TestView(View):
        @method_decorator(cache_per_user(60))
        def get(self, request, *args, **kwargs):
            return TestCachePerUser.TestResponse()

    def test_cache_per_user(self):
        view = TestCachePerUser.TestView()

        def mock_user_request(user_uuid):
            """
            Some nasty hackery to avoid Django handling the (Test) View invocation.
            Django ordinarily handles caching as part of it's URL lookup, dispatch
            and response mechanism. We however don't have a _real_ route mapping
            to this (Test) View.
            :param user_uuid:
            :return:
            """
            request = Request(HttpRequest())
            request.method = "GET"
            request.META["SERVER_NAME"] = "localhost"
            request.META["SERVER_PORT"] = 8080
            user = Mock()
            user.uuid = user_uuid
            request._user = user
            return request

        # Check caching for user1
        request_user1 = mock_user_request("uuid1")
        response_user1 = view.get(request_user1).render().content
        self.assertEqual(view.get(request_user1).render().content, response_user1)

        time.sleep(1)

        # Check caching for user2
        request_user2 = mock_user_request("uuid2")
        response_user2 = view.get(request_user2).render().content
        self.assertEqual(view.get(request_user2).render().content, response_user2)
        self.assertNotEqual(response_user1, response_user2)
