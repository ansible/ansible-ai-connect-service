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

from unittest import TestCase

import ansible_ai_connect.main.pipeline as pipeline


class TestPipeline(TestCase):
    def test_remove_pii(self):
        details = {
            "email": "",
            "fullname": "",
            "first_name": "",
            "last_name": "",
            "favorite_color": "chartreuse",
        }

        pipeline.remove_pii(None, details, None, None, None)
        self.assertEqual(
            details,
            {
                "favorite_color": "chartreuse",
            },
        )
