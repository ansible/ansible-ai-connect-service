import logging

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from social_core.exceptions import AuthCanceled
from social_core.pipeline.partial import partial
from social_core.pipeline.user import get_username
from social_django.models import UserSocialAuth

logger = logging.getLogger(__name__)


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
