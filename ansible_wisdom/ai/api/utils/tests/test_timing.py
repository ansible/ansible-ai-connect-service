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
