from django.core.management.base import BaseCommand
from oauth2_provider.models import get_application_model

Application = get_application_model()


class Command(BaseCommand):
    help = "Shortcut to update redirect URIs of an existing OAuth application"

    def add_arguments(self, parser):
        parser.add_argument(
            "--client-id",
            type=str,
            help="The ID of the existing application",
        )
        parser.add_argument(
            "--redirect-uris",
            type=str,
            help="The redirect URIs, this must be a space separated string e.g 'URI1 URI2'",
        )

    def handle(self, *args, **options):
        obj = Application.objects.get(client_id=options["client_id"])
        obj.redirect_uris = options["redirect_uris"]
        obj.save()
