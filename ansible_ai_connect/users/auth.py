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

import logging

import jwt
from django.conf import settings
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed
from social_core.backends.oauth import BaseOAuth2PKCE
from social_core.exceptions import AuthException
from social_django.models import UserSocialAuth
from social_django.utils import load_backend, load_strategy

from ansible_ai_connect.users.constants import (
    RHSSO_LIGHTSPEED_SCOPE,
    USER_SOCIAL_AUTH_PROVIDER_AAP,
)

logger = logging.getLogger("auth")


class AAPOAuth2(BaseOAuth2PKCE):
    """AAP OAuth authentication backend"""

    PKCE_DEFAULT_CODE_CHALLENGE_METHOD = "S256"

    name = USER_SOCIAL_AUTH_PROVIDER_AAP
    # SOCIAL_AUTH_AAP_USER_FIELDS

    AUTHORIZATION_URL = f"{settings.AAP_API_URL}/o/authorize/"
    ACCESS_TOKEN_URL = f"{settings.AAP_API_URL}/o/token/"
    ACCESS_TOKEN_METHOD = "POST"
    SCOPE_SEPARATOR = ","
    EXTRA_DATA = [("id", "id"), ("expires", "expires")]

    def get_user_details(self, response):
        """Return user details"""
        return {
            "username": response.get("username"),
            "email": response.get("email") or "",
            "first_name": response.get("first_name"),
            "login": response.get("username"),
        }

    def user_data(self, access_token, *args, **kwargs):
        """Loads user data from service"""
        url = self.get_me_endpoint(settings.AAP_API_URL)
        resp_data = self.get_json(url, headers={"Authorization": f"bearer {access_token}"})
        return resp_data.get("results")[0]

    def extra_data(self, user, uid, response, details=None, *args, **kwargs):
        """Overrides super extra_data to add license check"""
        data = super().extra_data(user, uid, response, details=details, *args, **kwargs)
        data["aap_licensed"] = self.user_has_valid_license(response.get("access_token"))
        data["aap_system_auditor"] = (
            response["is_system_auditor"] if "is_system_auditor" in response else False
        )
        data["aap_superuser"] = response["is_superuser"] if "is_superuser" in response else False
        return data

    def user_has_valid_license(self, access_token):
        url = self.get_config_endpoint(settings.AAP_API_URL)
        data = self.get_json(url, headers={"Authorization": f"bearer {access_token}"})
        license_info = data.get("license_info")
        if not license_info:
            return False
        if license_info.get("license_type", "UNLICENSED") == "open":
            return True
        return not license_info.get("date_expired")

    def get_me_endpoint(self, api_url):
        """Creates me link to the AAP API depending on the Auth platform"""

        # AAP Controller has /api at the end for API link, AAP Gateway doesn't
        url = api_url.rstrip("/")
        return f"{url}/v2/me/" if url.endswith("/api") else f"{url}/api/gateway/v1/me/"

    def get_config_endpoint(self, api_url):
        """Creates config link to the AAP API depending on the Auth platform"""

        # AAP Controller has /api at the end for API link, AAP Gateway doesn't
        url = api_url.rstrip("/")
        return f"{url}/v2/config/" if url.endswith("/api") else f"{url}/api/controller/v2/config/"


class RHSSOAuthentication(authentication.BaseAuthentication):
    """Red Hat SSO Access Token authentication backend"""

    @staticmethod
    def _reject(reason):
        """Reject an RHSSO credential without logging token contents."""
        logger.warning("RHSSO authentication failed: %s", reason)
        raise AuthenticationFailed("Invalid RHSSO access token")

    # This function works for validating the access token and
    # identifying an existing user. It doesn't work if user doesn't exist yet.
    def _auth_existing_user(self, access_token, request):
        strategy = load_strategy()
        backend = load_backend(strategy, "oidc", redirect_uri=None)
        key = backend.find_valid_key(access_token)
        if key is None:
            self._reject("signature verification failed")

        rsakey = jwt.PyJWK(key)

        # Decode and verify access token using extracted public key
        try:
            decoded_token = jwt.decode(
                access_token,
                rsakey.key,
                algorithms=["RS256"],
                issuer=backend.id_token_issuer(),
                audience=RHSSO_LIGHTSPEED_SCOPE,
            )
        except jwt.InvalidTokenError as e:
            # Includes expiry, issuer, audience, signature, and malformed-claim
            # failures. Keep these distinct from a token this backend cannot parse.
            self._reject(type(e).__name__)

        scope = decoded_token.get("scope")
        if not isinstance(scope, str) or RHSSO_LIGHTSPEED_SCOPE not in scope.split():
            self._reject("required scope is missing")

        social_user_id = decoded_token.get("sub")
        try:
            social_user = UserSocialAuth.objects.get(provider="oidc", uid=social_user_id)
            return social_user.user, decoded_token
        except UserSocialAuth.DoesNotExist:
            return None, decoded_token

    def authenticate(self, request):
        authorization_header = request.headers.get("Authorization")
        if not authorization_header:
            return None  # No token provided

        try:
            cred_type, access_token = authorization_header.split()
        except ValueError:
            return None  # Invalid Authorization header format

        if cred_type.lower() != "bearer":
            return None  # Wrong token type

        try:
            existing_user, user_data = self._auth_existing_user(access_token, request)
        except jwt.InvalidSignatureError:
            # InvalidSignatureError subclasses DecodeError, but a bad signature
            # is a rejected credential, not an unrecognized token.
            self._reject("signature verification failed")
        except jwt.DecodeError:
            # The token is not a decodable JWT for this backend. Let the rest of
            # the configured authentication chain decide whether it applies.
            return None

        if existing_user:
            return (existing_user, None)

        # Create the user from the already-validated token through the normal
        # social-auth pipeline. Passing the response directly avoids replacing
        # a method on the backend instance.
        strategy = load_strategy()
        backend = load_backend(strategy, "oidc", redirect_uri=None)
        response = {**user_data, "access_token": access_token}
        try:
            user = backend.strategy.authenticate(backend, response=response)
        except AuthException as e:
            self._reject(type(e).__name__)

        if user is None:
            self._reject("user provisioning did not return a user")

        return (user, None)
