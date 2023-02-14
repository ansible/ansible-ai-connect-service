from django.conf import settings
from django.views.generic import TemplateView
from rest_framework.authtoken.models import Token


class UserTemplateView(TemplateView):
    template_name = 'users/home.html'
    extra_context = {'pilot_docs_url': settings.PILOT_DOCS_URL}

    def get_context_data(self, **kwargs):
        kwargs = super().get_context_data(**kwargs)
        user = self.request.user
        if user.is_authenticated:
            kwargs['drf_token'] = Token.objects.get(user=user).key
        return kwargs
