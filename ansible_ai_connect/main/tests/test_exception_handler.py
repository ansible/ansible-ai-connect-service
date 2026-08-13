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

from http import HTTPStatus

from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import RequestFactory, SimpleTestCase
from rest_framework.exceptions import NotAuthenticated, ValidationError

from ansible_ai_connect.ai.api.exceptions import WisdomBadRequest
from ansible_ai_connect.main.exception_handler import exception_handler_with_error_type


class ExceptionHandlerWithErrorTypeTests(SimpleTestCase):
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()

    def _context(self):
        request = self.factory.get("/api/v1/service-index/resources/missing/")
        return {"request": request}

    def test_http404_returns_404_without_raising(self):
        """Missing resources must stay 404; do not crash into 500 (AAP-78941)."""
        response = exception_handler_with_error_type(
            Http404("No Resource matches"), self._context()
        )

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertIn("detail", response.data)

    def test_permission_denied_returns_403_without_raising(self):
        response = exception_handler_with_error_type(PermissionDenied(), self._context())

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_api_exception_is_still_reshaped(self):
        exc = WisdomBadRequest("bad input")
        response = exception_handler_with_error_type(exc, self._context())

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(response.data["code"], exc.default_code)
        self.assertEqual(response.data["message"], "bad input")
        self.assertEqual(response.error_type, exc.default_code)

    def test_drf_validation_error_is_still_reshaped(self):
        exc = ValidationError({"field": ["required"]})
        response = exception_handler_with_error_type(exc, self._context())

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(response.data["code"], "invalid")
        self.assertIn("field", response.data["detail"])

    def test_unhandled_exception_still_propagates_as_none(self):
        # DRF returns None for non-API exceptions → framework 500 path unchanged.
        response = exception_handler_with_error_type(RuntimeError("boom"), self._context())
        self.assertIsNone(response)

    def test_not_authenticated_is_still_reshaped(self):
        exc = NotAuthenticated()
        response = exception_handler_with_error_type(exc, self._context())

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
        self.assertEqual(response.data["code"], exc.default_code)
        self.assertEqual(response.error_type, exc.default_code)
