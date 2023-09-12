import logging

from django.conf import settings
from django.forms import Form
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.urls import reverse
from django.views.generic import TemplateView
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from social_django.utils import load_strategy

from .serializers import UserSerializer

logger = logging.getLogger(__name__)


class HomeView(TemplateView):
    template_name = 'users/home.html'


class UnauthorizedView(TemplateView):
    template_name = 'users/unauthorized.html'
    extra_context = {'signup_url': settings.SIGNUP_URL}


class CurrentUserView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class TermsOfService(TemplateView):
    template_name = None  # passed in via the urlpatterns
    extra_context = {
        'form': Form(),
    }

    def get(self, request, *args, **kwargs):
        partial_token = request.GET.get('partial_token')
        self.extra_context['partial_token'] = partial_token
        if partial_token is None:
            logger.warning('GET TermsOfService was invoked without partial_token')
            return HttpResponseForbidden()
        return super().get(request, args, kwargs)

    def post(self, request, *args, **kwargs):
        form = Form(request.POST)
        form.is_valid()
        partial_token = form.data.get('partial_token')
        if partial_token is None:
            logger.warning('POST TermsOfService was invoked without partial_token')
            return HttpResponseBadRequest()

        strategy = load_strategy()
        partial = strategy.partial_load(partial_token)
        if partial is None:
            logger.error('strategy.partial_load(partial_token) returned None')
            return HttpResponseBadRequest()

        accepted = request.POST.get('accepted') == 'True'
        request.session['terms_accepted'] = accepted
        request.session.save()

        backend = partial.backend
        complete = reverse("social:complete", kwargs={"backend": backend})
        return strategy.redirect(complete + f"?partial_token={partial.token}")
