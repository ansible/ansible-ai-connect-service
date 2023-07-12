import logging

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from social_core.exceptions import AuthCanceled
from social_core.pipeline.partial import partial
from social_core.pipeline.user import get_username
from social_django.models import UserSocialAuth

logger = logging.getLogger(__name__)


# Replace original get_username function to avoid a random hash at the end if
# user authenticates with more than one github provider.
def github_get_username(uid, strategy, details, backend, user=None, *args, **kwargs):
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
        if social_user.uid != str(uid):
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


def _terms_of_service(strategy, user, **kwargs):
    terms_accepted = strategy.session_get('terms_accepted', None)
    if user.date_terms_accepted is None:
        if terms_accepted is None:
            # We haven't gone through the flow yet -- go to the T&C page
            current_partial = kwargs.get('current_partial')
            terms_of_service = reverse('terms_of_service')
            return strategy.redirect(f'{terms_of_service}?partial_token={current_partial.token}')

        if not terms_accepted:
            raise AuthCanceled("Terms and conditions were not accepted.")

        # We've accepted the T&C, set the field on the user.
        user.date_terms_accepted = timezone.now()
        user.save()
        return {'terms_accepted': terms_accepted}

    # User had previously accepted, so short-circuit the T&C page.
    return {'terms_accepted': True}


@partial
def terms_of_service(strategy, details, user=None, is_new=False, *args, **kwargs):
    return _terms_of_service(strategy, user, **kwargs)
