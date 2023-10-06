from abc import abstractmethod

from ai.management.commands._base_wca_command import BaseWCACommand


class BaseWCADeleteCommand(BaseWCACommand):
    def do_command(self, client, args, options):
        org_id = options["org_id"]
        client.delete_secret(org_id, self.get_secret_suffix())
        self.stdout.write(self.get_success_message(org_id))

    @abstractmethod
    def get_success_message(self, org_id) -> str:
        # Abstract method
        pass
