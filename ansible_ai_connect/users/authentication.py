from ansible_base.jwt_consumer.common.auth import JWTAuthentication


class LightspeedJWTAuthentication(JWTAuthentication):

    def authenticate(self, request):
        userdata = super().authenticate(request)
        if userdata:
            user, _ = userdata
            user.aap_user = True
            user.save()
        return userdata

    def process_permissions(self):
        # Prevent processing of RBAC permissions
        pass
