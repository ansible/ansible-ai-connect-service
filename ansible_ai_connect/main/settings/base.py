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

"""
Django settings for main project.

Generated by 'django-admin startproject' using Django 4.1.3.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.1/ref/settings/
"""

import json
import logging
import os
import sys
from importlib.resources import files
from pathlib import Path
from typing import cast

from ansible_ai_connect.main.settings.legacy import load_from_env_vars
from ansible_ai_connect.main.settings.types import (
    t_deployment_mode,
    t_one_click_reports_postman_type,
    t_wca_secret_backend_type,
)

logger = logging.getLogger(__name__)

BASE_DIR: Path = files("ansible_ai_connect")
ANSIBLE_AI_PROJECT_NAME = os.getenv("ANSIBLE_AI_PROJECT_NAME") or "Ansible AI Connect"
ANSIBLE_AI_CHATBOT_NAME = (
    os.getenv("ANSIBLE_AI_CHATBOT_NAME") or "Ansible Lightspeed Intelligent Assistant"
)

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.1/howto/deployment/checklist/

SECRET_KEY = os.environ["SECRET_KEY"]

ALLOWED_HOSTS = ["localhost"]

# Application definition

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",  # Used by the admin dashboard
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "social_django",
    "ansible_ai_connect.users",
    "ansible_ai_connect.organizations",
    "ansible_ai_connect.ai",
    "django_prometheus",
    "drf_spectacular",
    "django_extensions",
    "health_check",
    "health_check.db",
    "ansible_ai_connect.healthcheck",
    "oauth2_provider",
    "import_export",
    "ansible_base.resource_registry",
    "ansible_base.jwt_consumer",
]

MIDDLEWARE = [
    "allow_cidr.middleware.AllowCIDRMiddleware",
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "oauth2_provider.middleware.OAuth2TokenMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "social_django.middleware.SocialAuthExceptionMiddleware",
    "ansible_ai_connect.main.middleware.SegmentMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
    "csp.middleware.CSPMiddleware",
]

if os.environ.get("CSRF_TRUSTED_ORIGINS"):
    CSRF_TRUSTED_ORIGINS = os.environ.get("CSRF_TRUSTED_ORIGINS").split(",")
else:
    CSRF_TRUSTED_ORIGINS = ["http://localhost:8000"]

# Allow Prometheus to scrape metrics
ALLOWED_CIDR_NETS = [os.environ.get("ALLOWED_CIDR_NETS", "10.0.0.0/8")]

AUTH_USER_MODEL = "users.User"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"
LOGIN_ERROR_URL = "login"

ANSIBLE_AI_ENABLE_TECH_PREVIEW = (
    os.getenv("ANSIBLE_AI_ENABLE_TECH_PREVIEW", "False").lower() == "true"
)

SIGNUP_URL = os.environ.get("SIGNUP_URL", "https://www.redhat.com/en/engage/project-wisdom")
COMMERCIAL_DOCUMENTATION_URL = os.getenv(
    "COMMERCIAL_DOCUMENTATION_URL",
    "https://access.redhat.com/documentation/en-us/"
    "red_hat_ansible_lightspeed_with_ibm_watsonx_code_assistant/2.x_latest",
)
TERMS_NOT_APPLICABLE = os.environ.get("TERMS_NOT_APPLICABLE", False)

SOCIAL_AUTH_GITHUB_KEY = None
SOCIAL_AUTH_GITHUB_TEAM_KEY = None
if os.environ.get("SOCIAL_AUTH_GITHUB_TEAM_KEY"):
    SOCIAL_AUTH_GITHUB_TEAM_KEY = os.environ.get("SOCIAL_AUTH_GITHUB_TEAM_KEY")
    SOCIAL_AUTH_GITHUB_TEAM_SECRET = os.environ.get("SOCIAL_AUTH_GITHUB_TEAM_SECRET")
    SOCIAL_AUTH_GITHUB_TEAM_ID = os.environ.get("SOCIAL_AUTH_GITHUB_TEAM_ID") or 7188893
    SOCIAL_AUTH_GITHUB_TEAM_SCOPE = ["read:org"]
    SOCIAL_AUTH_GITHUB_TEAM_EXTRA_DATA = ["login"]
elif os.environ.get("SOCIAL_AUTH_GITHUB_KEY"):
    SOCIAL_AUTH_GITHUB_KEY = os.environ.get("SOCIAL_AUTH_GITHUB_KEY")
    SOCIAL_AUTH_GITHUB_SECRET = os.environ.get("SOCIAL_AUTH_GITHUB_SECRET")
    SOCIAL_AUTH_GITHUB_SCOPE = [""]
    SOCIAL_AUTH_GITHUB_EXTRA_DATA = ["login"]

SOCIAL_AUTH_JSONFIELD_ENABLED = True
SOCIAL_AUTH_LOGIN_ERROR_URL = "/unauthorized/"


def is_ssl_enabled(value: str) -> bool:
    """SSL should be enabled if value is not recognized"""
    disabled = value.lower() in ("false", "f", "0", "-1")
    return not disabled


AAP_API_URL = os.environ.get("AAP_API_URL")
AAP_API_PROVIDER_NAME = os.environ.get("AAP_API_PROVIDER_NAME", "Ansible Automation Platform")
SOCIAL_AUTH_VERIFY_SSL = is_ssl_enabled(os.getenv("SOCIAL_AUTH_VERIFY_SSL", "True"))
SOCIAL_AUTH_AAP_KEY = os.environ.get("SOCIAL_AUTH_AAP_KEY")
SOCIAL_AUTH_AAP_SECRET = os.environ.get("SOCIAL_AUTH_AAP_SECRET")
SOCIAL_AUTH_AAP_SCOPE = ["read"]
SOCIAL_AUTH_AAP_EXTRA_DATA = ["login"]

SOCIAL_AUTH_OIDC_OIDC_ENDPOINT = os.environ.get("SOCIAL_AUTH_OIDC_OIDC_ENDPOINT")
SOCIAL_AUTH_OIDC_KEY = os.environ.get("SOCIAL_AUTH_OIDC_KEY")
SOCIAL_AUTH_OIDC_SECRET = os.environ.get("SOCIAL_AUTH_OIDC_SECRET")
SOCIAL_AUTH_OIDC_SCOPE = ["api.lightspeed"]
SOCIAL_AUTH_OIDC_EXTRA_DATA = [("preferred_username", "login")]

AUTHZ_BACKEND_TYPE = os.environ.get("AUTHZ_BACKEND_TYPE")
AUTHZ_SSO_CLIENT_ID = os.environ.get("AUTHZ_SSO_CLIENT_ID")
AUTHZ_SSO_CLIENT_SECRET = os.environ.get("AUTHZ_SSO_CLIENT_SECRET")
AUTHZ_SSO_SERVER = os.environ.get("AUTHZ_SSO_SERVER")
AUTHZ_API_SERVER = os.environ.get("AUTHZ_API_SERVER")
AUTHZ_SSO_TOKEN_SERVICE_TIMEOUT = float(os.getenv("AUTHZ_SSO_TOKEN_SERVICE_TIMEOUT") or "1.0")
AUTHZ_SSO_TOKEN_SERVICE_RETRY_COUNT = int(os.getenv("AUTHZ_SSO_TOKEN_SERVICE_RETRY_COUNT") or "3")
AUTHZ_AMS_SERVICE_RETRY_COUNT = int(os.getenv("AMS_SERVICE_RETRY_COUNT") or "3")
AUTHZ_AMS_SERVICE_TIMEOUT = float(os.getenv("AUTHZ_AMS_SERVICE_TIMEOUT") or "3.0")

DEPLOYMENT_MODE: t_deployment_mode = cast(
    t_deployment_mode, os.environ.get("DEPLOYMENT_MODE") or "saas"
)
AUTHENTICATION_BACKENDS = [
    "social_core.backends.open_id_connect.OpenIdConnectAuth",
    "ansible_ai_connect.users.auth.AAPOAuth2",
    "django.contrib.auth.backends.ModelBackend",
    "oauth2_provider.backends.OAuth2Backend",
]
if os.environ.get("SOCIAL_AUTH_GITHUB_TEAM_KEY"):
    AUTHENTICATION_BACKENDS.append("social_core.backends.github.GithubTeamOAuth2")
elif os.environ.get("SOCIAL_AUTH_GITHUB_KEY"):
    AUTHENTICATION_BACKENDS.append("social_core.backends.github.GithubOAuth2")

SOCIAL_AUTH_PIPELINE = (
    "ansible_ai_connect.users.pipeline.block_auth_users",
    "social_core.pipeline.social_auth.social_details",
    "social_core.pipeline.social_auth.social_uid",
    "social_core.pipeline.social_auth.social_user",
    "ansible_ai_connect.main.pipeline.remove_pii",
    "social_core.pipeline.social_auth.auth_allowed",
    "ansible_ai_connect.users.pipeline.github_get_username",
    # 'social_core.pipeline.user.get_username',
    "social_core.pipeline.user.create_user",
    "ansible_ai_connect.users.pipeline.redhat_organization",
    "social_core.pipeline.social_auth.associate_user",
    "social_core.pipeline.user.user_details",
    "ansible_ai_connect.users.pipeline.load_extra_data",
)

# Wisdom Eng Team:
# gh api -H "Accept: application/vnd.github+json" /orgs/ansible/teams/wisdom-contrib

# Write key for sending analytics data to Segment. Note that each of Prod/Dev have a different key.
SEGMENT_WRITE_KEY = os.environ.get("SEGMENT_WRITE_KEY")
SEGMENT_ANALYTICS_WRITE_KEY = os.environ.get("SEGMENT_ANALYTICS_WRITE_KEY")
ANALYTICS_MIN_ANSIBLE_EXTENSION_VERSION = os.environ.get(
    "ANALYTICS_MIN_ANSIBLE_EXTENSION_VERSION", "v2.12.143"
)

OAUTH2_PROVIDER = {
    "SCOPES": {
        "read": "Read basic user information",
        "write": "Request Ansible content suggestions",
    },
    "ALLOWED_REDIRECT_URI_SCHEMES": [
        "http",
        "https",
        "vscode",
        "vscodium",
        "vscode-insiders",
        "code-oss",
        "checode",
    ],
    # 14 hours, to match the duration of the Red Hat SSO sessions
    "REFRESH_TOKEN_EXPIRE_SECONDS": 50_400,
}

#
# We need to run 'manage.py migrate' before adding our own OAuth2 application model.
# See https://django-oauth-toolkit.readthedocs.io/en/latest/advanced_topics.html
# #extending-the-application-model
#
# Also, if these lines are executed in testing, test fails with:
#   django.db.utils.ProgrammingError: relation "users_user" does not exist
#
if sys.argv[1:2] not in [["migrate"], ["test"]]:
    INSTALLED_APPS.append("ansible_ai_connect.wildcard_oauth2")
    OAUTH2_PROVIDER_APPLICATION_MODEL = "wildcard_oauth2.Application"

# OAUTH: todo
# - remove ansible_wisdom/users/auth.py module
# - remove ansible_wisdom/users/views.py module
# - remove "Authentication Token" line from ansible_wisdom/users/templates/users/home.html

COMPLETION_USER_RATE_THROTTLE = os.environ.get("COMPLETION_USER_RATE_THROTTLE") or "10/minute"
ME_USER_CACHE_TIMEOUT_SEC = int(os.environ.get("ME_USER_CACHE_TIMEOUT_SEC", 30))
ME_USER_RATE_THROTTLE = os.environ.get("ME_USER_RATE_THROTTLE") or "50/minute"
SPECIAL_THROTTLING_GROUPS = ["test"]
CHAT_RATE_THROTTLE = os.environ.get("CHAT_RATE_THROTTLE") or "10/minute"

AMS_ORG_CACHE_TIMEOUT_SEC = int(os.environ.get("AMS_ORG_CACHE_TIMEOUT_SEC", 60 * 60 * 24))
AMS_SUBSCRIPTION_CACHE_TIMEOUT_SEC = int(
    os.environ.get("AMS_SUBSCRIPTION_CACHE_TIMEOUT_SEC", 60 * 15)
)

MULTI_TASK_MAX_REQUESTS = os.environ.get("MULTI_TASK_MAX_REQUESTS", 10)

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "DEFAULT_THROTTLE_CLASSES": ["ansible_ai_connect.users.throttling.GroupSpecificThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "user": COMPLETION_USER_RATE_THROTTLE,
        "test": "100000/minute",
        "me": ME_USER_RATE_THROTTLE,
        "chat": CHAT_RATE_THROTTLE,
    },
    "PAGE_SIZE": 10,
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "oauth2_provider.contrib.rest_framework.OAuth2Authentication",
        "rest_framework.authentication.SessionAuthentication",
        "ansible_ai_connect.users.authentication.LightspeedJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "ansible_ai_connect.main.exception_handler."
    "exception_handler_with_error_type",
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.NamespaceVersioning",
    "ALLOWED_VERSIONS": ("v0", "v1"),
    "DEFAULT_VERSION": "v1",
    "VERSION_PARAM": "version",
}

API_VERSION = "1.0.0"

# ==========================================
# Django Ansible Base configuration
# ------------------------------------------
ANSIBLE_BASE_ORGANIZATION_MODEL = "ansible_ai_connect.organizations.models.Organization"
ANSIBLE_BASE_RESOURCE_CONFIG_MODULE = "ansible_ai_connect.ai.resource_api"
ANSIBLE_BASE_REST_FILTERS_RESERVED_NAMES = (
    "page",
    "page_size",
    "format",
    "order",
    "order_by",
    "search",
    "type",
    "host_filter",
    "count_disabled",
    "no_truncate",
    "limit",
    "validate",
)

ANSIBLE_BASE_JWT_KEY = os.getenv("ANSIBLE_BASE_JWT_KEY")
ANSIBLE_BASE_JWT_VALIDATE_CERT = (
    os.getenv("ANSIBLE_BASE_JWT_VALIDATE_CERT", "False").lower() == "true"
) or False
ANSIBLE_BASE_MANAGED_ROLE_REGISTRY = json.loads(
    os.getenv("ANSIBLE_BASE_MANAGED_ROLE_REGISTRY", "{}")
)

RESOURCE_SERVER__URL = os.getenv("RESOURCE_SERVER__URL")
RESOURCE_SERVER__SECRET_KEY = os.getenv("RESOURCE_SERVER__SECRET_KEY")
RESOURCE_SERVER__VALIDATE_HTTPS = os.getenv("RESOURCE_SERVER__VALIDATE_HTTPS")
# ==========================================

# Current RHSSOAuthentication implementation is incompatible with tech preview terms partial
if not ANSIBLE_AI_ENABLE_TECH_PREVIEW:
    REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"].insert(
        -1, "ansible_ai_connect.users.auth.RHSSOAuthentication"
    )

ROOT_URLCONF = "ansible_ai_connect.main.urls"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "{levelname} {asctime} {filename}:{funcName} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple", "level": "INFO"},
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "propagate": True,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "ansible_ai_connect.users.authz_checker": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "ansible_ai_connect.users.signals": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "ari_changes": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "auth": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "organizations": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "ansible_ai_connect.ai.api.streaming_chat": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.getenv("DJANGO_LOG_LEVEL") or "WARNING",
    },
}
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": list(BASE_DIR.glob("*/templates/")),
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "social_django.context_processors.backends",
            ],
        },
    },
]

WSGI_APPLICATION = "ansible_ai_connect.main.wsgi.application"
ASGI_APPLICATION = "ansible_ai_connect.main.asgi.application"

# Database
# https://docs.djangoproject.com/en/4.1/ref/settings/#databases
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["ANSIBLE_AI_DATABASE_NAME"],
        "USER": os.environ["ANSIBLE_AI_DATABASE_USER"],
        "PASSWORD": os.environ["ANSIBLE_AI_DATABASE_PASSWORD"],
        "HOST": os.environ["ANSIBLE_AI_DATABASE_HOST"],
        "PORT": os.getenv("ANSIBLE_AI_DATABASE_PORT") or 5432,
    }
}

# Password validation
# https://docs.djangoproject.com/en/4.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
# https://docs.djangoproject.com/en/4.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/

STATIC_URL = "static/"

# Absolute filesystem path to the directory where static file are collected via
# the collectstatic command.
STATIC_ROOT = "/var/www/wisdom/public/static"

# Paths to where static files that are not explicitly part of a
# particular Django app should be collected from.
STATICFILES_DIRS = list(BASE_DIR.glob("*/static/"))

# Default primary key field type
# https://docs.djangoproject.com/en/4.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

APPEND_SLASH = True

ENABLE_ARI_POSTPROCESS = os.getenv("ENABLE_ARI_POSTPROCESS", "False").lower() == "true"
ARI_BASE_DIR = os.getenv("ARI_KB_PATH") or "/etc/ari/kb/"
ARI_RULES_DIR = os.path.join(ARI_BASE_DIR, "rules")
ARI_DATA_DIR = os.path.join(ARI_BASE_DIR, "data")
ARI_RULES = [
    "P001",
    "P002",
    "P003",
    "P004",
    "W001",
    "W003",
    "W004",
    "W005",
    "W006",
    "W007",
    "W008",
    "W009",
    "W010",
    "W011",  # replace with_* loop with the modern loop:
    "W012",
    "W013",
    # "W014",  # anonymizer: already done by the ansible_wisdom app
    "W015",
    "W016",
    "W017",
    "W018",
    "W019",
    "W021",
    "W022",
    "W023",
    "W024",
    "W025",
    "W026",
    "W027",
]
if "ARI_RULES" in os.environ:
    ARI_RULES = os.environ["ARI_RULES"].split(",")
ARI_RULE_FOR_OUTPUT_RESULT = os.getenv("ARI_RULE_FOR_OUTPUT_RESULT") or "W007"

ENABLE_ANSIBLE_LINT_POSTPROCESS = (
    os.getenv("ENABLE_ANSIBLE_LINT_POSTPROCESS", "False").lower() == "true"
)

ANSIBLE_LINT_TRANSFORM_RULES = ["all"]

ENABLE_ADDITIONAL_CONTEXT = os.getenv("ENABLE_ADDITIONAL_CONTEXT", "False").lower() == "true"

LAUNCHDARKLY_SDK_KEY = os.getenv("LAUNCHDARKLY_SDK_KEY", "")
LAUNCHDARKLY_SDK_TIMEOUT = os.getenv("LAUNCHDARKLY_SDK_TIMEOUT", 20)

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "cache",
    }
}

WCA_SECRET_BACKEND_TYPE: t_wca_secret_backend_type = cast(t_wca_secret_backend_type, "aws_sm")

WCA_SECRET_MANAGER_ACCESS_KEY = os.getenv("WCA_SECRET_MANAGER_ACCESS_KEY", "")
WCA_SECRET_MANAGER_SECRET_ACCESS_KEY = os.getenv("WCA_SECRET_MANAGER_SECRET_ACCESS_KEY", "")
WCA_SECRET_MANAGER_KMS_KEY_ID = os.getenv("WCA_SECRET_MANAGER_KMS_KEY_ID", "")
WCA_SECRET_MANAGER_PRIMARY_REGION = os.getenv("WCA_SECRET_MANAGER_PRIMARY_REGION", "")
WCA_SECRET_MANAGER_REPLICA_REGIONS = [
    c.strip() for c in os.getenv("WCA_SECRET_MANAGER_REPLICA_REGIONS", "").split(",") if c
]

CSP_DEFAULT_SRC = ("'self'", "data:")
CSP_INCLUDE_NONCE_IN = ["script-src-elem"]
CSP_CONNECT_SRC = "'self'"

# Region for where the service is deployed. Used by the Health Check endpoint.
DEPLOYED_REGION = os.getenv("DEPLOYED_REGION") or "unknown"

# ==========================================
# Health checks
# ------------------------------------------
# Support to disable health checks. The default is that they are enabled.
# The naming convention in the existing settings is to ENABLE_XXX and not DISABLE_XXX.
ENABLE_HEALTHCHECK_SECRET_MANAGER = (
    os.getenv("ENABLE_HEALTHCHECK_SECRET_MANAGER", "True").lower() == "true"
)
ENABLE_HEALTHCHECK_AUTHORIZATION = (
    os.getenv("ENABLE_HEALTHCHECK_AUTHORIZATION", "True").lower() == "true"
)
ENABLE_HEALTHCHECK_ATTRIBUTION = (
    os.getenv("ENABLE_HEALTHCHECK_ATTRIBUTION", "True").lower() == "true"
)
# ==========================================

# ==========================================
# Metrics
# ------------------------------------------
# Follow AWX naming for this environment variable
# It is used to protect Prometheus's /metrics endpoint
ALLOW_METRICS_FOR_ANONYMOUS_USERS = (
    os.getenv("ALLOW_METRICS_FOR_ANONYMOUS_USERS", "True").lower() == "true"
)
# ==========================================

# ==========================================
# One-click/trial
# ------------------------------------------
ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL = (
    os.getenv("ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL", "False").lower() == "true"
)

ANSIBLE_AI_ONE_CLICK_REPORTS_POSTMAN: t_one_click_reports_postman_type = cast(
    t_one_click_reports_postman_type, os.getenv("ANSIBLE_AI_ONE_CLICK_REPORTS_POSTMAN") or "none"
)
ANSIBLE_AI_ONE_CLICK_REPORTS_CONFIG: dict = (
    json.loads(os.getenv("ANSIBLE_AI_ONE_CLICK_REPORTS_CONFIG"), strict=False)
    if os.getenv("ANSIBLE_AI_ONE_CLICK_REPORTS_CONFIG")
    else {}
)
# ==========================================

# ==========================================
# Chatbot
# ------------------------------------------
CHATBOT_DEFAULT_PROVIDER = os.getenv("CHATBOT_DEFAULT_PROVIDER")
CHATBOT_DEBUG_UI = os.getenv("CHATBOT_DEBUG_UI", "False").lower() == "true"
CHATBOT_DEFAULT_SYSTEM_PROMPT = os.getenv("CHATBOT_DEFAULT_SYSTEM_PROMPT")
# ==========================================

# ==========================================
# Playbook Generation/Explanation endpoints
# ------------------------------------------
ANSIBLE_AI_ENABLE_PLAYBOOK_ENDPOINT = (
    os.getenv("ANSIBLE_AI_ENABLE_PLAYBOOK_ENDPOINT", "True").lower() == "true"
)
# ==========================================

# ==========================================
# Pipeline configuration
# ------------------------------------------
model_pipeline_config = os.getenv("ANSIBLE_AI_MODEL_MESH_CONFIG")
ANSIBLE_AI_MODEL_MESH_CONFIG = (
    load_from_env_vars() if model_pipeline_config is None else model_pipeline_config
)
# ==========================================

# ==========================================
# Role Generation/Explanation endpoints
# ------------------------------------------
ANSIBLE_AI_ENABLE_ROLE_GEN_ENDPOINT = (
    os.getenv("ANSIBLE_AI_ENABLE_ROLE_GEN_ENDPOINT", "False").lower() == "true"
) or False
# ==========================================
