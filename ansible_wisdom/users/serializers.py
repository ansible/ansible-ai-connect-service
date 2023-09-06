from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'has_seat',
            'is_org_admin',
            'is_org_lightspeed_subscriber',
            'username',
        ]
