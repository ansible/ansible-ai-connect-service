from abc import abstractmethod

from ai.management.commands._base_wca_command import BaseWCACommand


class BaseWCAGetCommand(BaseWCACommand):
    def do_command(self, client, args, options):
        org_id = options["org_id"]
        response = client.get_secret(org_id, self.get_secret_suffix())
        if response is None:
            self.stdout.write(self.get_message_not_found(org_id))
            return

        self.stdout.write(self.get_message_found(org_id, response))

    @abstractmethod
    def get_message_found(self, org_id, response) -> str:
        pass

    @abstractmethod
    def get_message_not_found(self, org_id) -> str:
        pass
