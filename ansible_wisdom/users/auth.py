import logging

import jwt
from django.conf import settings
from jose import jwk
from rest_framework import authentication
from social_core.backends.oauth import BaseOAuth2
from social_django.models import UserSocialAuth
from social_django.utils import load_backend, load_strategy

from ansible_wisdom.users.constants import (
    RHSSO_LIGHTSPEED_SCOPE,
    USER_SOCIAL_AUTH_PROVIDER_AAP,
)

logger = logging.getLogger("auth")


class AAPOAuth2(BaseOAuth2):
    """AAP OAuth authentication backend"""

    name = USER_SOCIAL_AUTH_PROVIDER_AAP
    # SOCIAL_AUTH_AAP_USER_FIELDS

    AUTHORIZATION_URL = f'{settings.AAP_API_URL}/o/authorize/'
    ACCESS_TOKEN_URL = f'{settings.AAP_API_URL}/o/token/'
    ACCESS_TOKEN_METHOD = 'POST'
    SCOPE_SEPARATOR = ','
    EXTRA_DATA = [('id', 'id'), ('expires', 'expires')]

    def get_user_details(self, response):
        """Return user details"""
        return {
            'username': response.get('username'),
            'email': response.get('email') or '',
            'first_name': response.get('first_name'),
            'login': response.get('username'),
        }

    def user_data(self, access_token, *args, **kwargs):
        """Loads user data from service"""
        url = f'{settings.AAP_API_URL}/v2/me/'
        resp_data = self.get_json(url, headers={"Authorization": f"bearer {access_token}"})
        return resp_data.get('results')[0]

    def extra_data(self, user, uid, response, details=None, *args, **kwargs):
        """Return access_token, token_type, and extra defined names to store in
        extra_data field"""
        data = super().extra_data(user, uid, response, details=details, *args, **kwargs)
        access_token = response.get('access_token')
        url = f'{settings.AAP_API_URL}/v2/config/'
        resp_data = self.get_json(url, headers={"Authorization": f"bearer {access_token}"})
        data['aap_licensed'] = not resp_data['license_info']['date_expired']
        return data


class RHSSOAuthentication(authentication.BaseAuthentication):
    """Red Hat SSO Access Token authentication backend"""

    # This function works for validating the access token and
    # identifying an existing user. It doesn't work if user doesn't exist yet.
    def _auth_existing_user(self, access_token, request):
        strategy = load_strategy()
        backend = load_backend(strategy, 'oidc', redirect_uri=None)
        key = backend.find_valid_key(access_token)
        rsakey = jwk.construct(key)

        # Decode and verify access token using extracted public key
        decoded_token = jwt.decode(
            access_token,
            rsakey.to_pem().decode("utf-8"),
            algorithms=['RS256'],
            issuer=backend.id_token_issuer(),
            audience=RHSSO_LIGHTSPEED_SCOPE,
        )

        scope = decoded_token.get("scope")
        if scope != RHSSO_LIGHTSPEED_SCOPE:
            raise ValueError(f"Unexpected scope: {scope}")

        social_user_id = decoded_token.get('sub')
        try:
            social_user = UserSocialAuth.objects.get(provider='oidc', uid=social_user_id)
            return social_user.user, decoded_token
        except UserSocialAuth.DoesNotExist:
            return None, decoded_token

    def authenticate(self, request):
        authorization_header = request.headers.get('Authorization')
        if not authorization_header:
            return None  # No token provided

        try:
            cred_type, access_token = authorization_header.split()
        except ValueError:
            return None  # Invalid Authorization header format

        if cred_type.lower() != 'bearer':
            return None  # Wrong token type

        try:
            existing_user, user_data = self._auth_existing_user(access_token, request)
        except Exception as e:
            logger.info(e)
            return None  # Problem decoding

        if existing_user:
            return (existing_user, None)

        # Create the user if he doesn't exist.
        # TODO - Consider always going through create flow if it's not
        # too slow. This will pick up changes in username and RH admin as well.
        strategy = load_strategy()
        backend = load_backend(strategy, 'oidc', redirect_uri=None)
        try:
            backend.user_data = lambda _: user_data
            user = backend.do_auth(access_token)
            return (user, None)
        except Exception as e:
            logger.info(e)
            return None
