import logging
from datetime import datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.forms import Form
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.urls import reverse
from django.views.generic import TemplateView
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from social_core.exceptions import AuthCanceled
from social_core.pipeline.partial import partial
from social_core.pipeline.user import get_username
from social_django.models import UserSocialAuth
from social_django.utils import load_strategy

from .serializers import UserSerializer

logger = logging.getLogger(__name__)


class HomeView(TemplateView):
    template_name = 'users/home.html'
    extra_context = {'pilot_docs_url': settings.PILOT_DOCS_URL}


class UnauthorizedView(TemplateView):
    template_name = 'users/unauthorized.html'
    extra_context = {'signup_url': settings.SIGNUP_URL}


class CurrentUserView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class TermsOfService(TemplateView):
    template_name = 'users/terms_of_service.html'
    extra_context = {
        'form': Form(),
    }

    def get(self, request, *args, **kwargs):
        partial_token = request.GET.get('partial_token')
        self.extra_context['partial_token'] = partial_token
        if partial_token is None:
            logger.error('GET /terms_of_service/ was invoked without partial_token')
            return HttpResponseForbidden()
        return super().get(request, args, kwargs)

    def post(self, request, *args, **kwargs):
        form = Form(request.POST)
        form.is_valid()
        partial_token = form.data.get('partial_token')
        if partial_token is None:
            logger.error('POST /terms_of_service/ was invoked without partial_token')
            return HttpResponseBadRequest()

        accepted = request.POST.get('accepted') == 'True'

        strategy = load_strategy()
        partial = strategy.partial_load(partial_token)
        if partial is None:
            logger.error('strategy.partial_load(partial_token) returned None')
            return HttpResponseBadRequest()
        backend = partial.backend

        if accepted:
            request.session['date_terms_accepted'] = datetime.now()
            request.session.save()

        complete = reverse("social:complete", kwargs={"backend": backend})
        return strategy.redirect(complete + f"?partial_token={partial.token}")


def _terms_of_service(strategy, **kwargs):
    request = kwargs['request']
    date_terms_accepted = request.session.get('date_terms_accepted')
    if date_terms_accepted is not None:
        # if date_terms_accepted is a dummy value (== datetime.max), it indicates the
        # user did not accept our terms and conditions. Raise an AuthCanceled
        # in such a case.
        if date_terms_accepted == datetime.max:
            del request.session['date_terms_accepted']
            request.session.save()
            raise AuthCanceled('Terms and conditions were not accepted.')

        # if a non-dummy value is set in term_accepted, it means that the user
        # accepted our terms and conditions. Return to the original auth flow.
        return
    # insert a dummy value to 'date_terms_accepted' date in session
    request.session['date_terms_accepted'] = datetime.max

    current_partial = kwargs.get('current_partial')
    terms_of_service = reverse('terms_of_service')
    return strategy.redirect(f'{terms_of_service}?partial_token={current_partial.token}')


@partial
def terms_of_service(strategy, details, user=None, is_new=False, *args, **kwargs):
    return _terms_of_service(strategy, **kwargs)


def _add_date_accepted(strategy, user, **kwargs):
    request = kwargs['request']
    date_terms_accepted = request.session.get('date_terms_accepted')
    if (
        user
        and user.date_terms_accepted is None
        and date_terms_accepted is not None
        and date_terms_accepted != datetime.max
    ):
        user.date_terms_accepted = date_terms_accepted
        user.save()
    return


@partial
def add_date_accepted(strategy, details, user=None, is_new=False, *args, **kwargs):
    return _add_date_accepted(strategy, user, **kwargs)


# Replace original get_username function to avoid a random hash at the end if
# user authenticates with more than one github provider. This needs to be revisited
# when we add additional providers like Red Hat SSO.
def github_get_username(uid, strategy, details, backend, user=None, *args, **kwargs):
    if backend.name not in ['github', 'github-team']:
        logger.warn(f"Unexpected: auth backend {backend.name}")
        return get_username(strategy, details, backend, user, *args, **kwargs)

    # If django user is already known, fall back to default behavior
    if user:
        # Fallback to default behavior
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
