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

from ansible_wisdom.test_utils import WisdomServiceLogAwareTestCase
from ansible_wisdom.users.signals import _obfuscate


class TestSignals(WisdomServiceLogAwareTestCase):
    def test_obfuscate(self):
        self.assertEqual("*", _obfuscate("x"))
        self.assertEqual("**", _obfuscate("sh"))
        self.assertEqual("***", _obfuscate("spy"))
        self.assertEqual("h**e", _obfuscate("hide"))
        self.assertEqual("h****n", _obfuscate("hidden"))
        self.assertEqual("to******et", _obfuscate("top-secret"))
        self.assertEqual("a-lo***************alue", _obfuscate("a-long-top-secret-value"))
