from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'rh_org_has_subscription',
            'rh_user_has_seat',
            'rh_user_is_org_admin',
            'username',
        ]
