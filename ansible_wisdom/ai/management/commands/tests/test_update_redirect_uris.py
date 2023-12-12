import secrets
import string

from django.core.management import call_command
from django.test import TestCase
from oauth2_provider.models import get_application_model

N = 40

Application = get_application_model()

REDIRECT_URIS = "vscode://redhat.ansible"
NEW_REDIRECT_URIS = REDIRECT_URIS + " https://*.github.dev/extension-auth-callback"


class UpdateRedirectURICommandTest(TestCase):
    def setUp(self):
        self.client_id = ''.join(
            secrets.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits)
            for i in range(N)
        )
        call_command(
            "createapplication",
            "public",
            "authorization-code",
            name="Ansible Lightspeed for VS Code",
            client_id=self.client_id,
            redirect_uris=REDIRECT_URIS,
        )

    def tearDown(self):
        obj = Application.objects.get(client_id=self.client_id)
        obj.delete()

    def test_success(self):
        call_command(
            "update_redirect_uris", client_id=self.client_id, redirect_uris=NEW_REDIRECT_URIS
        )
        obj = Application.objects.get(client_id=self.client_id)
        self.assertEqual(obj.redirect_uris, NEW_REDIRECT_URIS)

    def test_success_with_no_change(self):
        call_command("update_redirect_uris", client_id=self.client_id, redirect_uris=REDIRECT_URIS)
        obj = Application.objects.get(client_id=self.client_id)
        self.assertEqual(obj.redirect_uris, REDIRECT_URIS)

    def test_application_not_found(self):
        with self.assertRaises(Exception) as exc:
            call_command(
                "update_redirect_uris",
                client_id="****INVALID_CLIENT_ID****",
                redirect_uris=NEW_REDIRECT_URIS,
            )
        self.assertEqual(str(exc.exception), "Application matching query does not exist.")
