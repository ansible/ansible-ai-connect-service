from django.core.exceptions import ValidationError
from django.test import TestCase

from ..models import Application, validate_uris

redirect_uris = [
    'vscode://redhat.ansible',
    r'https://.*\.github\.dev/extension-auth-callback?.*',
    r'http://.*/.*?.*',
]


class _AppLabel:
    app_label = 'wildcard_oauth2'


class WildcardOAuth2Test(TestCase):
    def setUp(self):
        self.app = Application(redirect_uris=' '.join(redirect_uris))

    def test_standalone_vscode_callback_uri(self):
        rc = self.app.redirect_uri_allowed('vscode://redhat.ansible')
        self.assertTrue(rc)
        self.app.clean()

    def test_invalid_callback_uri(self):
        rc = self.app.redirect_uri_allowed('vscode://othercompany.ansible')
        self.assertFalse(rc)

    def test_valid_codespases_callback_uri(self):
        rc = self.app.redirect_uri_allowed(
            'https://jubilant-engine-wv4w5xw9vq9f9gg9.github.dev/'
            'extension-auth-callback?state=6766a56164972ebe9ab0350c00d9041c'
        )
        self.assertTrue(rc)

    def test_invalid_codespases_callback_uri(self):
        rc = self.app.redirect_uri_allowed(
            'https://jubilant-engine-wv4w5xw9vq9f9gg9.github.com/'
            'extension-auth-callback?state=6766a56164972ebe9ab0350c00d9041c'
        )
        self.assertFalse(rc)

    def test_valid_code_server_callback_uri(self):
        rc = self.app.redirect_uri_allowed(
            'http://localhost:18080/stable-9658969084238651b6dde258e04f4abd9b14bfd1/callback'
            '?vscode-reqid=2&vscode-scheme=code-oss&vscode-authority=redhat.ansible'
        )
        self.assertTrue(rc)


class ValidateUrisTest(TestCase):
    def test_uri_no_error(self):
        validate_uris('https://example.com/callback')

    def test_uri_containing_fragment(self):
        try:
            validate_uris('https://example.com/callback#fragment')
        except ValidationError as e:
            self.assertEqual(e.message, 'Redirect URIs must not contain fragments')

    def test_uri_containing_invalid_scheme(self):
        try:
            validate_uris('myapp://example.com/callback')
        except ValidationError as e:
            self.assertEqual(e.message, 'Redirect URI scheme is not allowed.')

    def test_uri_containing_no_domain(self):
        try:
            validate_uris('vscode:redhat.ansible')
        except ValidationError as e:
            self.assertEqual(e.message, 'Redirect URI must contain a domain.')
