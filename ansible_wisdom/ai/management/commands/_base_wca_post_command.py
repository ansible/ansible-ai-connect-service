from ai.management.commands._base_wca_command import BaseWCACommand


class BaseWCAPostCommand(BaseWCACommand):
    def do_command(self, client, args, options):
        org_id = options["org_id"]
        secret = options["secret"]
        key_name = client.save_secret(org_id, self.get_secret_suffix(), secret)
        self.stdout.write(self.get_success_message(org_id, key_name))

    def get_success_message(self, org_id, key_name) -> str:
        pass
