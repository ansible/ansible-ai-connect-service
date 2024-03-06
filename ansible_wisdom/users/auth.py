from django.conf import settings
from rest_framework.authentication import TokenAuthentication
from social_core.backends.oauth import BaseOAuth2

from ansible_wisdom.users.constants import USER_SOCIAL_AUTH_PROVIDER_AAP


class BearerTokenAuthentication(TokenAuthentication):
    """Use 'Bearer' keyword in Authorization header rather than 'Token' for DRF token auth"""

    keyword = "Bearer"


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
