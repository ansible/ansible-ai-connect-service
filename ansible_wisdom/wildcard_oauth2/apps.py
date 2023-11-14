"""
Django App Configuration
"""

from django.apps import AppConfig


class WildcardOauth2ApplicationConfig(AppConfig):
    """
    Configures wildcard_oauth2 as a Django app plugin
    """

    name = 'wildcard_oauth2'
    verbose_name = "Wildcard OAuth2 Application"
