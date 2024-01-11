import logging

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from jose import jwk
from organizations.models import Organization
from social_core.exceptions import AuthCanceled, AuthException
from social_core.pipeline.partial import partial
from social_core.pipeline.user import get_username
from social_django.models import UserSocialAuth

logger = logging.getLogger(__name__)


# Replace original get_username function to avoid a random hash at the end if
# user authenticates with more than one github provider.
def github_get_username(strategy, details, backend, user=None, *args, **kwargs):
    if backend.name not in ['github', 'github-team']:
        return get_username(strategy, details, backend, user, *args, **kwargs)

    # If django user is already known, fall back to default behavior
    if user:
        return get_username(strategy, details, backend, user, *args, **kwargs)

    github_username = details.get('username')
    User = get_user_model()

    # If there's no django user with this username yet, we can use it
    if not User.objects.filter(username=github_username).exists():
        # No django user with this username yet
        return {'username': github_username}

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
        if social_user.uid != str(kwargs['uid']):
            same_user = False
            break
        if social_user.provider not in ['github', 'github-team']:
            same_user = False
            break

    if same_user:
        # Allow the username to pass through.
        return {'username': github_username}

    else:
        # This doesn't really need to be a warn. This can happen in acceptable scenarios, like a
        # userchanges his GitHub ID and somebody then adopts it, or a Red Hat SSO user collides
        # with a GitHub user.But I think it might be worth calling out in case of questions from
        # users and my own curiosity.
        logger.warn(f"GitHub user {github_username} collides with an existing django user")
        # Fallback to default behavior
        return get_username(strategy, details, backend, user, *args, **kwargs)


def redhat_organization(backend, user, response, *args, **kwargs):
    if backend.name != 'oidc':
        return
    if not backend.id_token:
        logger.error("Missing id_token, cannot get the organization id.")
        return

    key = backend.find_valid_key(response['access_token'])
    rsakey = jwk.construct(key)
    payload = jwt.decode(
        response['access_token'],
        rsakey.to_pem().decode("utf-8"),
        algorithms=[key['alg']],
        audience="account",
    )

    realm_access = payload.get("realm_access", {})
    roles = realm_access.get("roles", [])
    user.external_username = payload.get("preferred_username")
    user.rh_user_is_org_admin = 'admin:org:all' in roles

    if settings.AUTHZ_BACKEND_TYPE == "dummy":
        if settings.AUTHZ_DUMMY_RH_ORG_ADMINS == "*":
            user.rh_user_is_org_admin |= True
        elif isinstance(settings.AUTHZ_DUMMY_RH_ORG_ADMINS, str):
            org_admin_users = settings.AUTHZ_DUMMY_RH_ORG_ADMINS.split(",")
            user.rh_user_is_org_admin |= user.external_username in org_admin_users
        else:
            logger.error("AUTHZ_DUMMY_RH_ORG_ADMINS has an invalid format.")

    user.organization = Organization.objects.get_or_create(
        id=backend.id_token['organization']['id']
    )[0]
    user.save()
    return {
        'organization_id': user.organization.id,
        'rh_user_is_org_admin': user.rh_user_is_org_admin,
        'external_username': user.external_username,
    }


def _terms_of_service(strategy, user, backend, **kwargs):
    accepted = 'terms_accepted'
    is_commercial = user.rh_user_has_seat
    if settings.TERMS_NOT_APPLICABLE or is_commercial:
        # Commercial & local users are not presented with T&C page in login flow (new and existing users)
        return {accepted: True}

    field_name = 'community_terms_accepted'
    view_name = 'community_terms'
    terms_accepted = strategy.session_get(accepted, None)
    if getattr(user, field_name, None) is not None:
        # User had previously accepted, so short-circuit the T&C page.
        return {accepted: True}

    if terms_accepted is None:
        # We haven't gone through the flow yet -- go to the T&C page
        current_partial = kwargs.get('current_partial')
        return strategy.redirect(f'{reverse(view_name)}?partial_token={current_partial.token}')

    if not terms_accepted:
        raise AuthCanceled("Terms and conditions were not accepted.")

    # We've accepted the T&C, set the field on the user.
    setattr(user, field_name, timezone.now())
    user.save()
    return {accepted: terms_accepted}


@partial
def terms_of_service(strategy, details, backend, user=None, is_new=False, *args, **kwargs):
    return _terms_of_service(strategy, user, backend, **kwargs)


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
