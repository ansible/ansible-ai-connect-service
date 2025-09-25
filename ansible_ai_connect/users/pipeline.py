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
from django.contrib.auth import get_user_model
from social_core.exceptions import AuthException
from social_core.pipeline.user import get_username
from social_django.models import UserSocialAuth

from ansible_ai_connect.ai.api.utils.segment import send_segment_group
from ansible_ai_connect.organizations.models import ExternalOrganization
from ansible_ai_connect.users.constants import RHSSO_LIGHTSPEED_SCOPE

logger = logging.getLogger(__name__)


# Replace original get_username function to avoid a random hash at the end if
# user authenticates with more than one github provider.
def github_get_username(strategy, details, backend, user=None, *args, **kwargs):
    if backend.name not in ["github", "github-team"]:
        return get_username(strategy, details, backend, user, *args, **kwargs)

    # If django user is already known, fall back to default behavior
    if user:
        return get_username(strategy, details, backend, user, *args, **kwargs)

    github_username = details.get("username")
    User = get_user_model()

    # If there's no django user with this username yet, we can use it
    if not User.objects.filter(username=github_username).exists():
        # No django user with this username yet
        return {"username": github_username}

    # There is an existing django user with this username. We need to determine if he
    # is the same as the user logging in now. Ensure he only has github social auth users associated
    # and that they have the same uid as him.

    existing_user = User.objects.get(username=github_username)
    # Get the social auth users associated with this django user (there may be multiple)
    social_auth_users = UserSocialAuth.objects.filter(user=existing_user.id)
    if not social_auth_users.exists():
        logger.warn(
            f"Unexpected: django user found with no social auth - username {github_username}"  # noqa: E501
        )
        # Fallback to default behavior
        return get_username(strategy, details, backend, user, *args, **kwargs)

    # Loop through the social users and confirm they are github users with same uid
    same_user = True
    for social_user in social_auth_users:
        if social_user.uid != str(kwargs["uid"]):
            same_user = False
            break
        if social_user.provider not in ["github", "github-team"]:
            same_user = False
            break

    if same_user:
        # Allow the username to pass through.
        return {"username": github_username}

    else:
        # This doesn't really need to be a warn. This can happen in acceptable scenarios, like a
        # userchanges his GitHub ID and somebody then adopts it, or a Red Hat SSO user collides
        # with a GitHub user.But I think it might be worth calling out in case of questions from
        # users and my own curiosity.
        logger.warn(f"GitHub user {github_username} collides with an existing django user")
        # Fallback to default behavior
        return get_username(strategy, details, backend, user, *args, **kwargs)


def is_rh_email_domain(email) -> bool:
    email_domain: str = email[email.find("@") + 1 :] if email else None
    return email_domain.lower() == "redhat.com" if email_domain else False


def is_rh_internal_user(user) -> bool:
    return is_rh_email_domain(user.email) and bool(user.email_verified)


def redhat_organization(backend, user, response, *args, **kwargs):
    if backend.name != "oidc":
        return

    key = backend.find_valid_key(response["access_token"])
    rsakey = jwt.PyJWK(key)
    payload = jwt.decode(
        response["access_token"],
        rsakey.key,
        algorithms=[key.get("alg", "RS256")],
        audience=RHSSO_LIGHTSPEED_SCOPE,
    )

    realm_access = payload.get("realm_access", {})
    roles = realm_access.get("roles", [])
    user.external_username = payload.get("preferred_username")
    user.name = payload.get("name")
    user.given_name = payload.get("given_name")
    user.family_name = payload.get("family_name")
    user.email = payload.get("email")
    user.email_verified = payload.get("email_verified")
    user.rh_user_is_org_admin = "admin:org:all" in roles
    user.rh_internal = is_rh_internal_user(user)

    if settings.AUTHZ_BACKEND_TYPE == "dummy":
        if settings.AUTHZ_DUMMY_RH_ORG_ADMINS == "*":
            user.rh_user_is_org_admin |= True
        elif isinstance(settings.AUTHZ_DUMMY_RH_ORG_ADMINS, str):
            org_admin_users = settings.AUTHZ_DUMMY_RH_ORG_ADMINS.split(",")
            user.rh_user_is_org_admin |= user.external_username in org_admin_users
        else:
            logger.error("AUTHZ_DUMMY_RH_ORG_ADMINS has an invalid format.")

    user.organization = ExternalOrganization.objects.get_or_create(
        id=int(payload["organization"]["id"])
    )[0]
    user.save()
    send_segment_group(
        f"rhsso-{user.organization.id}", "Red Hat Organization", user.organization.id, user
    )
    return {
        "external_username": user.external_username,
        "organization_id": user.organization.id,
        "rh_internal": user.rh_internal,
        "rh_user_is_org_admin": user.rh_user_is_org_admin,
    }


class AuthAlreadyLoggedIn(AuthException):
    def __str__(self):
        return "User already logged in"


def block_auth_users(backend=None, details=None, response=None, user=None, *args, **kwargs):
    """Safeguard to be sure user won't get multiple providers"""
    if user:
        raise AuthAlreadyLoggedIn(backend)


def load_extra_data(backend, details, response, uid, user, *args, **kwargs):
    social = kwargs.get("social") or backend.strategy.storage.user.get_social_auth(
        backend.name, uid
    )
    if social:
        extra_data = backend.extra_data(user, uid, response, details, *args, **kwargs)
        user.external_username = extra_data.get("login")
        user.save()
        social.extra_data["aap_licensed"] = (
            extra_data.get("aap_licensed") if user.is_aap_user() else False
        )
        social.extra_data["aap_system_auditor"] = (
            extra_data.get("aap_system_auditor") if user.is_aap_user() else False
        )
        social.extra_data["aap_superuser"] = (
            extra_data.get("aap_superuser") if user.is_aap_user() else False
        )
        social.save()
