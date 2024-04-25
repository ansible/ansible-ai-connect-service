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

from unittest import TestCase, mock

import ansible_wisdom.ai.api.utils.timing as timing


class TestTiming(TestCase):
    @mock.patch("timeit.default_timer")
    def test_time_activity(self, default_timer):
        activity = "🚀"
        with self.assertLogs(logger="root", level="INFO") as log:
            default_timer.side_effect = [0, -1]
            with timing.time_activity(activity):
                pass
            self.assertCountEqual(
                [
                    f"INFO:ansible_wisdom.ai.api.utils.timing:[Timing]" f" {activity} start.",
                    f"INFO:ansible_wisdom.ai.api.utils.timing:[Timing]"
                    f" {activity} finished (Took -1.00s)",
                ],
                log.output,
            )
