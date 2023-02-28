from django.conf import settings
from django.shortcuts import render
from rest_framework.authtoken.models import Token


def home(request):
    user = request.user
    context = {'pilot_docs_url': settings.PILOT_DOCS_URL}
    if user.is_authenticated:
        token = Token.objects.get(user=user)
        context['drf_token'] = token.key
    return render(request, 'users/home.html', context)
