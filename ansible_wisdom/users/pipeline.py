import logging

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
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
    user.organization_id = backend.id_token['organization']['id']
    user.save()
    return {'organization_id': backend.id_token['organization']['id']}


def _terms_of_service(strategy, user, backend, **kwargs):
    # TODO: Not every usage of the Red Hat SSO is going to be
    # commercial, there also needs to be the seat check when that gets
    # integrated.  When that happens, update this to include that
    # logic.  Possibly also remove the Commerical group?
    is_commercial = user.has_seat
    terms_type = 'commercial' if backend.name == 'oidc' and is_commercial else 'community'
    field_name = f'{terms_type}_terms_accepted'
    view_name = f'{terms_type}_terms'

    terms_accepted = strategy.session_get('terms_accepted', None)
    if getattr(user, field_name, None) is None:
        if terms_accepted is None:
            # We haven't gone through the flow yet -- go to the T&C page
            current_partial = kwargs.get('current_partial')
            terms_of_service = reverse(view_name)
            return strategy.redirect(f'{terms_of_service}?partial_token={current_partial.token}')

        if not terms_accepted:
            raise AuthCanceled("Terms and conditions were not accepted.")

        # We've accepted the T&C, set the field on the user.
        setattr(user, field_name, timezone.now())
        user.save()
        return {'terms_accepted': terms_accepted}

    # User had previously accepted, so short-circuit the T&C page.
    return {'terms_accepted': True}


@partial
def terms_of_service(strategy, details, backend, user=None, is_new=False, *args, **kwargs):
    return _terms_of_service(strategy, user, backend, **kwargs)


def load_extra_data(backend, details, response, uid, user, *args, **kwargs):
    """Similar to the original load_extra_data, but with a filter on the fields to keep"""
    accepted_extra_data = ["login"]
    social = kwargs.get("social") or backend.strategy.storage.user.get_social_auth(
        backend.name, uid
    )
    if social:
        extra_data = backend.extra_data(user, uid, response, details, *args, **kwargs)
        extra_data = {k: v for k, v in extra_data.items() if k in accepted_extra_data}
        social.set_extra_data(extra_data)


class AuthAlreadyLoggedIn(AuthException):
    def __str__(self):
        return "User already logged in"


def block_auth_users(backend=None, details=None, response=None, user=None, *args, **kwargs):
    """Safeguard to be sure user won't get multiple providers"""
    if user:
        raise AuthAlreadyLoggedIn(backend)
