from ai.management.commands._base_wca_command import BaseWCACommand


class BaseWCADeleteCommand(BaseWCACommand):
    def __do_command(self, client, *args, **options):
        org_id = options["org_id"]
        client.delete_secret(org_id, self.__get_secret_suffix())
        self.stdout.write(self.__get_success_message())

    def __get_success_message(self, org_id) -> str:
        pass
