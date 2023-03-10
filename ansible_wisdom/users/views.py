from django.conf import settings
from django.views.generic import TemplateView
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated

from .serializers import UserSerializer

# OAUTH: remove when switched
if not settings.OAUTH2_ENABLE:
    from rest_framework.authtoken.models import Token


class HomeView(TemplateView):
    template_name = 'users/home.html'
    extra_context = {'pilot_docs_url': settings.PILOT_DOCS_URL}

    # OAUTH: remove when switched
    if not settings.OAUTH2_ENABLE:

        def get_context_data(self, **kwargs):
            kwargs = super().get_context_data(**kwargs)
            user = self.request.user
            if user.is_authenticated:
                kwargs['drf_token'] = Token.objects.get(user=user).key
            return kwargs


class CurrentUserView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user
