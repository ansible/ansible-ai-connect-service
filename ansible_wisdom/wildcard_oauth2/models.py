"""
A custom OAuth2 application that allows wildcard for redirect_uris

https://github.com/jazzband/django-oauth-toolkit/issues/443#issuecomment-420255286
"""
import re
from urllib.parse import parse_qsl, unquote, urlparse

from django.core.exceptions import ValidationError
from oauth2_provider.models import AbstractApplication
from oauth2_provider.settings import oauth2_settings


def validate_uris(value):
    """Ensure that `value` contains valid blank-separated URIs."""
    urls = value.split()
    for url in urls:
        obj = urlparse(url)
        if obj.fragment:
            raise ValidationError('Redirect URIs must not contain fragments')
        if obj.scheme.lower() not in oauth2_settings.ALLOWED_REDIRECT_URI_SCHEMES:
            raise ValidationError('Redirect URI scheme is not allowed.')
        if not obj.netloc:
            raise ValidationError('Redirect URI must contain a domain.')


class Application(AbstractApplication):
    """Subclass of application to allow for regular expressions for the redirect uri."""

    @staticmethod
    def _uri_is_allowed(allowed_uri, uri):
        """Check that the URI conforms to these rules."""
        schemes_match = allowed_uri.scheme == uri.scheme
        netloc_matches_pattern = re.fullmatch(allowed_uri.netloc, uri.netloc)

        # The original code allowed only fixed paths only with:
        #   paths_match = allowed_uri.path == uri.path
        # However, since paths can contain variable portions (e.g. code-server),
        # code was modified to support regex patterns in paths as well.
        paths_match = re.fullmatch(allowed_uri.path, uri.path)

        return all([schemes_match, netloc_matches_pattern, paths_match])

    def __init__(self, *args, **kwargs):
        """Relax the validator to allow for uris with regular expressions."""
        self._meta.get_field('redirect_uris').validators = [
            validate_uris,
        ]
        super().__init__(*args, **kwargs)

    def redirect_uri_allowed(self, uri):
        """
        Check if given url is one of the items in :attr:`redirect_uris` string.
        A Redirect uri domain may be a regular expression e.g. `^(.*).example.com$` will
        match all subdomains of example.com.
        A Redirect uri may be `https://(.*).example.com/some/path/?q=x`
        :param uri: Url to check
        """
        for allowed_uri in self.redirect_uris.split():
            parsed_allowed_uri = urlparse(allowed_uri)
            parsed_uri = urlparse(uri)

            if self._uri_is_allowed(parsed_allowed_uri, parsed_uri):
                aqs_set = set(parse_qsl(parsed_allowed_uri.query))
                uqs_set = set(parse_qsl(parsed_uri.query))

                if aqs_set.issubset(uqs_set):
                    return True

        return False

    def clean(self):
        uris_with_wildcard = [uri for uri in self.redirect_uris.split(' ') if '*' in uri]
        if uris_with_wildcard:
            self.redirect_uris = ' '.join(
                [uri for uri in self.redirect_uris.split(' ') if '*' not in uri]
            )
        super().clean()
        if uris_with_wildcard:
            self.redirect_uris += ' ' + ' '.join(uris_with_wildcard)

    def is_usable(self, request):
        # This is a hacky way to decode redirect_uri stored in an oauthlib.Request instance.
        # Once the oauthlib.Request class started decoding redirect_uri correctly, this will
        # be removed.
        if getattr(request, '_params'):
            redirect_uri = request._params.get('redirect_uri')
            if redirect_uri:
                request._params['redirect_uri'] = unquote(redirect_uri)

        return True

    class Meta:
        db_table = 'oauth2_provider_application'
        # Without the following line, tests fail with:
        #   RuntimeError: Model class wildcard_oauth2.models.Application doesn't declare
        #   an explicit app_label and isn't in an application in INSTALLED_APPS.
        app_label = 'wildcard_oauth2'
