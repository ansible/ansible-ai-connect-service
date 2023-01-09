#!/usr/bin/env python3

from datetime import datetime
from django.test import TestCase

import ai.api.views as views


class CompletionsTestCase(TestCase):
    def test_rate_limit_ok(self):
        session = {}
        self.assertEqual(views.rate_limit(session), False)
        self.assertIn("last_call", session)

    def test_rate_limit_ko(self):
        session = {"last_call": datetime.now().isoformat()}
        self.assertEqual(views.rate_limit(session), True)
