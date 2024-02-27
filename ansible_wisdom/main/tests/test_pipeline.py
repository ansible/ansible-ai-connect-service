from unittest import TestCase

import ansible_wisdom.main.pipeline as pipeline


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
