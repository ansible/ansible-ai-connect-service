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

from .base import *  # NOQA
from .base import API_VERSION, MIDDLEWARE, cast, os
from .types import t_wca_secret_backend_type

DEBUG = True

ALLOWED_HOSTS = ["*"]

if DEBUG:
    SPECTACULAR_SETTINGS = {
        "TITLE": f"{ANSIBLE_AI_PROJECT_NAME}.",  # noqa: F405
        "DESCRIPTION": "Equip the automation developer at Lightspeed.",
        "VERSION": API_VERSION,
        "SERVE_INCLUDE_SCHEMA": False,
        "SERVERS": [
            {
                "url": "https://lightspeed-instance/api/v1",
                "description": "Direct access to a Lightspeed instance",
            },
            {
                "url": "https://aap/api/lightspeed/v1",
                "description": "Access through an Ansible Automation Platfrom gateway",
            },
        ],
        # OTHER SETTINGS
        "TAGS": [
            {"name": "ai", "description": "AI-related operations"},
            {"name": "me", "description": "Authenticated user information"},
            {"name": "wca", "description": "watsonx Code Assistant"},
        ],
        "SCHEMA_PATH_PREFIX": r"/api/v[0-9]+",
        "SCHEMA_PATH_PREFIX_TRIM": True,
        "PREPROCESSING_HOOKS": [
            "ansible_ai_connect.ai.api.openapi.preprocessing_filter_spec",
            "ansible_base.api_documentation.preprocessing_hooks.collect_ai_description_metadata",
        ],
        "POSTPROCESSING_HOOKS": [
            "ansible_base.api_documentation.postprocessing_hooks.add_x_ai_description",
        ],
    }

    # social_django does not process auth exceptions when DEBUG=True by default.
    # Following is for overriding the social_django middleware so that auth exceptions
    # are processed by middleware even when DEBUG=True.
    if "social_django.middleware.SocialAuthExceptionMiddleware" in MIDDLEWARE:  # noqa: F405
        index = MIDDLEWARE.index(  # noqa: F405
            "social_django.middleware.SocialAuthExceptionMiddleware"
        )
        MIDDLEWARE[index] = (
            "ansible_ai_connect.main.middleware.WisdomSocialAuthExceptionMiddleware"  # noqa: F405
        )

CSP_REPORT_ONLY = True
AUTHZ_BACKEND_TYPE = os.getenv("AUTHZ_BACKEND_TYPE") or "dummy"
# e.g:
# AUTHZ_BACKEND_TYPE="dummy"
# AUTHZ_DUMMY_RH_ORG_ADMINS=gleboude1@redhat.com
# note: "*" means that all the users from org with a subscription.
AUTHZ_DUMMY_RH_ORG_ADMINS = os.getenv("AUTHZ_DUMMY_RH_ORG_ADMINS", "")
# You can get your account number on this page
# https://www.redhat.com/wapps/ugc/protected/account.html
# note: "*" means that all the orgs have a subscription.
AUTHZ_DUMMY_ORGS_WITH_SUBSCRIPTION = os.getenv("AUTHZ_DUMMY_ORGS_WITH_SUBSCRIPTION", "")

WCA_SECRET_BACKEND_TYPE: t_wca_secret_backend_type = os.getenv("WCA_SECRET_BACKEND_TYPE") or cast(
    t_wca_secret_backend_type, "dummy"
)
# a list of key:value with a , separator. key is the orgid, value is the secret.
# when a secret with the string "valid", it means the backend will accept it has
# a valid string. e.g:
# WCA_SECRET_DUMMY_SECRETS=1009103:valid,11009104:not-valid
WCA_SECRET_DUMMY_SECRETS = os.getenv("WCA_SECRET_DUMMY_SECRETS", "")

# "Schema 2" Telemetry Admin Dashboard URL
TELEMETRY_ADMIN_DASHBOARD_URL = (
    "https://console.stage.redhat.com/ansible/lightspeed-admin-dashboard"
)

ANSIBLE_AI_ENABLE_PLAYBOOK_ENDPOINT = True
ANSIBLE_AI_ENABLE_ROLE_GEN_ENDPOINT = True
