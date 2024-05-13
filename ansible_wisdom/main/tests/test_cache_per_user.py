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

import time
from unittest.mock import Mock

from django.test import TestCase
from django.utils.decorators import method_decorator
from django.views.generic.base import View
from rest_framework.request import HttpRequest, Request
from rest_framework.response import Response

from ansible_ai_connect.main.cache.cache_per_user import cache_per_user


class TestCachePerUser(TestCase):
    class TestResponse(Response):
        @property
        def rendered_content(self):
            return f"timestamp={time.time()}"

    class TestView(View):
        @method_decorator(cache_per_user(60))
        def get(self, request, *args, **kwargs):
            return TestCachePerUser.TestResponse()

    @staticmethod
    def mock_request(user_uuid=None):
        """
        Some nasty hackery to avoid Django handling the (Test) View invocation.
        Django ordinarily handles caching as part of it's URL lookup, dispatch
        and response mechanism. We however don't have a _real_ route mapping
        to this (Test) View.
        :param user_uuid: User UUID for User. If None, no User will be associated with the Request
        :return:
        """
        request = Request(HttpRequest())
        request.method = "GET"
        request.META["SERVER_NAME"] = "localhost"
        request.META["SERVER_PORT"] = 8080

        if user_uuid:
            user = Mock()
            user.uuid = user_uuid
            request._user = user

        return request

    def test_cache_per_authenticated_user(self):
        view = TestCachePerUser.TestView()

        # Check caching for user1
        request_user1 = TestCachePerUser.mock_request("uuid1")
        response_user1 = view.get(request_user1).render().content
        self.assertEqual(view.get(request_user1).render().content, response_user1)

        time.sleep(1)

        # Check caching for user2
        request_user2 = TestCachePerUser.mock_request("uuid2")
        response_user2 = view.get(request_user2).render().content
        self.assertEqual(view.get(request_user2).render().content, response_user2)
        self.assertNotEqual(response_user1, response_user2)

    def test_cache_per_unauthenticated_user(self):
        view = TestCachePerUser.TestView()

        # Check no caching for anonymous requests
        request1 = TestCachePerUser.mock_request()
        response1 = view.get(request1).render().content
        self.assertIsNotNone(response1)

        time.sleep(1)

        request2 = TestCachePerUser.mock_request()
        response2 = view.get(request2).render().content
        self.assertNotEqual(response1, response2)
