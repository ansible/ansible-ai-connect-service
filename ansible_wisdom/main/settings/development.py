import os

from .base import *  # NOQA

DEBUG = True

ALLOWED_HOSTS = ["*"]

if DEBUG:
    SPECTACULAR_SETTINGS = {
        'TITLE': 'Ansible Lightspeed with IBM watsonx Code Assistant.',
        'DESCRIPTION': 'Equip the automation developer at Lightspeed.',
        'VERSION': '0.0.8',
        'SERVE_INCLUDE_SCHEMA': False,
        # OTHER SETTINGS
        'TAGS': [
            {"name": "ai", "description": "AI-related operations"},
            {"name": "me", "description": "Authenticated user information"},
            {"name": "check", "description": "Health check"},
            {"name": "wca", "description": "watsonx Code Assistant"},
        ],
        'SCHEMA_PATH_PREFIX': r'/api/v[0-9]+',
    }

    # social_django does not process auth exceptions when DEBUG=True by default.
    # Following is for overriding the social_django middleware so that auth exceptions
    # are processed by middleware even when DEBUG=True.
    if "social_django.middleware.SocialAuthExceptionMiddleware" in MIDDLEWARE:  # noqa: F405
        index = MIDDLEWARE.index(  # noqa: F405
            "social_django.middleware.SocialAuthExceptionMiddleware"
        )
        MIDDLEWARE[index] = (  # noqa: F405
            "ansible_wisdom.main.middleware.WisdomSocialAuthExceptionMiddleware"
        )

CSP_REPORT_ONLY = True
AUTHZ_BACKEND_TYPE = os.getenv("AUTHZ_BACKEND_TYPE") or "dummy"
# e.g:
# AUTHZ_BACKEND_TYPE="dummy"
# AUTHZ_DUMMY_USERS_WITH_SEAT=gleboude1@redhat.com
# AUTHZ_DUMMY_RH_ORG_ADMINS=gleboude1@redhat.com
# note: "*" means that all the users from org with a subscription.
AUTHZ_DUMMY_USERS_WITH_SEAT = os.getenv("AUTHZ_DUMMY_USERS_WITH_SEAT", "")
AUTHZ_DUMMY_RH_ORG_ADMINS = os.getenv("AUTHZ_DUMMY_RH_ORG_ADMINS", "")
# You can get your account number on this page
# https://www.redhat.com/wapps/ugc/protected/account.html
# note: "*" means that all the orgs have a subscription.
AUTHZ_DUMMY_ORGS_WITH_SUBSCRIPTION = os.getenv("AUTHZ_DUMMY_ORGS_WITH_SUBSCRIPTION", "")

WCA_SECRET_BACKEND_TYPE = os.getenv("WCA_SECRET_BACKEND_TYPE", "dummy")  # or aws_sm
# a list of key:value with a , separator. key is the orgid, value is the secret.
# when a secret with the string "valid", it means the backend will accept it has
# a valid string. e.g:
# WCA_SECRET_DUMMY_SECRETS=1009103:valid,11009104:not-valid
WCA_SECRET_DUMMY_SECRETS = os.getenv("WCA_SECRET_DUMMY_SECRETS", "")
WCA_CLIENT_BACKEND_TYPE = os.getenv("WCA_CLIENT_BACKEND_TYPE", "dummy")  # or wcaclient

# "Schema 2" Telemetry Admin Dashboard URL
TELEMETRY_ADMIN_DASHBOARD_URL = (
    "https://console.stage.redhat.com/ansible/lightspeed-admin-dashboard"
)
