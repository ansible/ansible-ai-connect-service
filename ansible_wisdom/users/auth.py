from rest_framework.authentication import TokenAuthentication


class BearerTokenAuthentication(TokenAuthentication):
    """Use 'Bearer' keyword in Authorization header rather than 'Token' for DRF token auth"""

    keyword = "Bearer"
