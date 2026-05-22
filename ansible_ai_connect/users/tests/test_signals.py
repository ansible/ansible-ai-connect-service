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

from unittest.mock import Mock, patch

from django.contrib.auth.signals import user_logged_in

from ansible_ai_connect.test_utils import WisdomServiceLogAwareTestCase
from ansible_ai_connect.users.signals import _obfuscate


class TestSignals(WisdomServiceLogAwareTestCase):
    def test_obfuscate(self):
        self.assertEqual("*", _obfuscate("x"))
        self.assertEqual("**", _obfuscate("sh"))
        self.assertEqual("***", _obfuscate("spy"))
        self.assertEqual("h**e", _obfuscate("hide"))
        self.assertEqual("h****n", _obfuscate("hidden"))
        self.assertEqual("to******et", _obfuscate("top-secret"))
        self.assertEqual("a-lo***************alue", _obfuscate("a-long-top-secret-value"))


class TestCSRFTokenRotationOnLogin(WisdomServiceLogAwareTestCase):

    @patch("ansible_ai_connect.users.signals.rotate_token")
    def test_csrf_token_rotated_on_login(self, mock_rotate_token):
        request = Mock()
        user = Mock()
        user_logged_in.send(sender=self.__class__, user=user, request=request)
        mock_rotate_token.assert_called_once_with(request)

    @patch("ansible_ai_connect.users.signals.rotate_token")
    def test_csrf_token_not_rotated_without_request(self, mock_rotate_token):
        user = Mock()
        user_logged_in.send(sender=self.__class__, user=user)
        mock_rotate_token.assert_not_called()
