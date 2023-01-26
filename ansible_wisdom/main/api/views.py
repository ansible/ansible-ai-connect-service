from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework import permissions
from rest_framework import viewsets

from ..serializers import GroupSerializer
from ..serializers import UserSerializer

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]


class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated]
