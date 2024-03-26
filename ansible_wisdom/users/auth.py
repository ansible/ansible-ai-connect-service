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

    is_license_expired = False

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

    def user_configs(self, access_token, *args, **kwargs):
        """Loads user data from service"""
        url = f'{settings.AAP_API_URL}/v2/config/'
        resp_data = self.get_json(url, headers={"Authorization": f"bearer {access_token}"})
        return resp_data

    def check_license_expiration(self, access_token, *args, **kwargs):
        data = self.user_configs(access_token, *args, **kwargs)
        return data['license_info']['date_expired']

    def auth_complete(self, *args, **kwargs):
        user = super().auth_complete(*args, **kwargs)
        user.is_onprem_license_expired = self.is_license_expired
        return user

    def do_auth(self, access_token, *args, **kwargs):
        self.is_license_expired = self.check_license_expiration(access_token, *args, **kwargs)
        return super().do_auth(access_token, *args, **kwargs)
