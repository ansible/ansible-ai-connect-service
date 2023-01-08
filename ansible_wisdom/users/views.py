from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.shortcuts import render
from rest_framework.authtoken.models import Token
from django.conf import settings


from social_django.utils import psa

from requests.exceptions import HTTPError

def home(request):
    user = request.user
    context = {'pilot_docs_url': settings.PILOT_DOCS_URL}
    if user.is_authenticated:
        token = Token.objects.get(user=user)
        context['drf_token'] = token.key
    return render(request, 'users/home.html', context)
