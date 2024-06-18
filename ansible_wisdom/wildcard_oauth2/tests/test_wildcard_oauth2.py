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

import re
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.test import TestCase

from ..models import (
    Application,
    is_acceptable_netloc,
    validate_uris,
    wildcard_string_to_regex,
)

redirect_uris = [
    "vscode://redhat.ansible",
    "https://*.github.dev/extension-auth-callback",
    "http://127.0.0.1:8080/*/callback",
    "https://*.openshiftapps.com/*/*/*/*/callback",
]


class WildcardOAuth2Test(TestCase):
    def setUp(self):
        super().setUp()
        self.app = Application(redirect_uris=" ".join(redirect_uris))

    def test_standalone_vscode_callback_uri(self):
        rc = self.app.redirect_uri_allowed("vscode://redhat.ansible")
        self.assertTrue(rc)
        self.app.clean()

    def test_invalid_callback_uri(self):
        rc = self.app.redirect_uri_allowed("vscode://othercompany.ansible")
        self.assertFalse(rc)

    def test_valid_codespases_callback_uri(self):
        rc = self.app.redirect_uri_allowed(
            "https://jubilant-engine-wv4w5xw9vq9f9gg9.github.dev/"
            "extension-auth-callback?state=6766a56164972ebe9ab0350c00d9041c"
        )
        self.assertTrue(rc)

    def test_invalid_codespases_callback_uri(self):
        rc = self.app.redirect_uri_allowed(
            "https://jubilant-engine-wv4w5xw9vq9f9gg9.github.com/"
            "extension-auth-callback?state=6766a56164972ebe9ab0350c00d9041c"
        )
        self.assertFalse(rc)

    def test_valid_dev_speces_callback_uri(self):
        rc = self.app.redirect_uri_allowed(
            "https://devspaces.apps.sandbox-m2.ll9k.p1.openshiftapps.com/"
            "rh-ee-ttakamiy/ansible-demo/3100/oss-dev/callback?"
            "vscode-reqid=3&vscode-scheme=checode&vscode-authority=redhat.ansible"
        )
        self.assertTrue(rc)

    def test_valid_code_server_callback_uri(self):
        rc = self.app.redirect_uri_allowed(
            "http://127.0.0.1:8080/stable-9658969084238651b6dde258e04f4abd9b14bfd1/callback"
            "?vscode-reqid=2&vscode-scheme=code-oss&vscode-authority=redhat.ansible"
        )
        self.assertTrue(rc)


class ValidateUrisTest(TestCase):
    def test_uri_no_error(self):
        validate_uris(
            "https://example.com/callback "
            "https://*.github.dev/extension-auth-callback?.* "
            "http://127.0.0.1:8000/.*?.*"
        )

    def test_uri_containing_fragment(self):
        try:
            validate_uris("https://example.com/callback#fragment")
        except ValidationError as e:
            self.assertEqual(e.message, "Redirect URIs must not contain fragments")

    def test_uri_containing_invalid_scheme(self):
        try:
            validate_uris("myapp://example.com/callback")
        except ValidationError as e:
            self.assertEqual(e.message, "Redirect URI scheme is not allowed.")

    def test_uri_containing_no_domain(self):
        try:
            validate_uris("vscode:redhat.ansible")
        except ValidationError as e:
            self.assertEqual(e.message, "Redirect URI must contain a domain.")

    def test_uri_containing_wildcard_in_root_domain(self):
        try:
            validate_uris("https://*.github.*/extension-auth-callback?.*")
        except ValidationError as e:
            self.assertEqual(e.message, "Redirect URI is not acceptable.")

    def test_ip_address(self):
        allowed_uri = urlparse("http://*.0.1/callback")
        uri = urlparse("http://123.123.0.1/callback")
        self.assertFalse(Application._uri_is_allowed(allowed_uri, uri))


class AcceptableNetlocTest(TestCase):
    def test_valid_netlocs(self):
        self.assertTrue(is_acceptable_netloc("subdomain.example.com"))
        self.assertTrue(is_acceptable_netloc("*.example.com"))
        self.assertTrue(is_acceptable_netloc("sub*.example.com"))
        self.assertTrue(is_acceptable_netloc("*sub.example.com"))
        self.assertTrue(is_acceptable_netloc("*sub*.sub.example.com"))
        self.assertTrue(is_acceptable_netloc("*.*.example.com"))

    def test_invalid_netlocs(self):
        self.assertFalse(is_acceptable_netloc("subdomain.*.com"))
        self.assertFalse(is_acceptable_netloc("*.example.*"))
        self.assertFalse(is_acceptable_netloc("sub*.example*.com"))
        self.assertFalse(is_acceptable_netloc("*.com"))


class WildcardStringToRegExTest(TestCase):
    def test_wildcard_string_to_regex(self):
        self.assertEqual(wildcard_string_to_regex("*"), "[^\\/]*")
        p = wildcard_string_to_regex("*sub*.sub.example.com")
        self.assertEqual(p, "[^\\/]*sub[^\\/]*\\.sub\\.example\\.com")
        self.assertTrue(re.match(p, "sub.sub.example.com"))
        self.assertTrue(re.match(p, "abcsubxyz.sub.example.com"))
        self.assertTrue(re.match(p, "abc.sub.sub.example.com"))
        self.assertFalse(re.match(p, "sub/xyz.sub.example.com"))
