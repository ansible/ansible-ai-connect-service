from ai.api.wca.views import WCAKeyView
from django.urls import path

urlpatterns = [path('<str:org_id>/apikey', WCAKeyView.as_view(), name='wca')]
