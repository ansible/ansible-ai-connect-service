from django.conf import settings
from django.shortcuts import render
from requests.exceptions import HTTPError
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from social_django.utils import psa


def home(request):
    user = request.user
    context = {'pilot_docs_url': settings.PILOT_DOCS_URL}
    if user.is_authenticated:
        token = Token.objects.get(user=user)
        context['drf_token'] = token.key
    return render(request, 'users/home.html', context)
