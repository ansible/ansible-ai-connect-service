#!/usr/bin/env python3

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
import unittest
from unittest.mock import Mock

from django.contrib.auth.models import AnonymousUser

from ansible_ai_connect.ai.api.views import AACSAPIView
from ansible_ai_connect.test_utils import WisdomServiceAPITestCaseBaseOIDC


class TestAACSAPIViewAnonymousUser(unittest.TestCase):

    def test_get_model_name_anonymous(self):

        m_request = Mock()
        m_request.user = AnonymousUser()
        model_name = AACSAPIView.get_model_name(m_request, None)
        self.assertIsNone(model_name)


class TestAACSAPIViewRegularUser(WisdomServiceAPITestCaseBaseOIDC):

    def test_get_model_name(self):

        m_request = Mock()
        m_request.user = self.user
        model_name = AACSAPIView.get_model_name(m_request, "my_req_model_id")
        self.assertEqual(model_name, "my_req_model_id")
