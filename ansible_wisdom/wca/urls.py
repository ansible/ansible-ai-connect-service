from django.urls import path
from wca.views import WCAKeyView

urlpatterns = [path('<str:org_id>/', WCAKeyView.as_view(), name='wca')]
