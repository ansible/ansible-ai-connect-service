from ai.management.commands._base_wca_command import BaseWCACommand


class BaseWCAGetCommand(BaseWCACommand):
    def __do_command(self, client, *args, **options):
        org_id = options["org_id"]
        response = client.get_secret(org_id, self.__get_secret_suffix())
        if response is None:
            self.stdout.write(self.__get_message_not_found())
            return

        self.stdout.write(self.__get_message_found())

    def __get_message_found(self, org_id, response) -> str:
        pass

    def __get_message_not_found(self, org_id) -> str:
        pass
