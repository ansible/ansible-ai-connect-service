from django.conf import settings
from rest_framework.authentication import TokenAuthentication
from social_core.backends.oauth import BaseOAuth2


class BearerTokenAuthentication(TokenAuthentication):
    """Use 'Bearer' keyword in Authorization header rather than 'Token' for DRF token auth"""

    keyword = "Bearer"


class AAPOAuth2(BaseOAuth2):
    """AAP OAuth authentication backend"""

    name = 'aap'
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
        # {
        #     "count": 1,
        #     "next": null,
        #     "previous": null,
        #     "results": [
        #         {
        #             "id": 3,
        #             "type": "user",
        #             "url": "/api/v2/users/3/",
        #             "related": {
        #                 "teams": "/api/v2/users/3/teams/",
        #                 "organizations": "/api/v2/users/3/organizations/",
        #                 "admin_of_organizations": "/api/v2/users/3/admin_of_organizations/",
        #                 "projects": "/api/v2/users/3/projects/",
        #                 "credentials": "/api/v2/users/3/credentials/",
        #                 "roles": "/api/v2/users/3/roles/",
        #                 "activity_stream": "/api/v2/users/3/activity_stream/",
        #                 "access_list": "/api/v2/users/3/access_list/",
        #                 "tokens": "/api/v2/users/3/tokens/",
        #                 "authorized_tokens": "/api/v2/users/3/authorized_tokens/",
        #                 "personal_tokens": "/api/v2/users/3/personal_tokens/"
        #             },
        #             "summary_fields": {
        #                 "user_capabilities": {
        #                     "edit": true,
        #                     "delete": false
        #                 }
        #             },
        #             "created": "2024-01-26T17:28:17.070899Z",
        #             "modified": "2024-01-29T16:09:42.272731Z",
        #             "username": "lightspeed-bot",
        #             "first_name": "Lightspeed",
        #             "last_name": "",
        #             "email": "",
        #             "is_superuser": false,
        #             "is_system_auditor": false,
        #             "password": "$encrypted$",
        #             "ldap_dn": "",
        #             "last_login": "2024-01-29T16:09:42.272731Z",
        #             "external_account": null,
        #             "auth": []
        #         }
        #     ]
        # }
        # TODO: check AAP license
        # url = f'{settings.AAP_API_URL}/v2/config/'
        # license = self.get_json(url, headers={"Authorization": f"bearer {access_token}"})
        # license.get('license_info')['date_expired']

        url = f'{settings.AAP_API_URL}/v2/me/'
        resp_data = self.get_json(url, headers={"Authorization": f"bearer {access_token}"})
        return resp_data.get('results')[0]
