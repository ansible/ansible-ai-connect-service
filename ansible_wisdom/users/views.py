from ai.api.serializers import AICompletionSerializer
from django.conf import settings
from django.views.generic import TemplateView
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

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


class CompletionsAdmin(APIView):
    permission_classes = [IsAdminUser]
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "completions.html"

    def get(self, request) -> Response:
        serializer = AICompletionSerializer()
        return Response({"serializer": serializer})
        # NOTE: Add model status the the response headers?
        # response = model_mesh_client.status(model_name=model_name)
