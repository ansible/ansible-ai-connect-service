#!/usr/bin/env python3

#  Copyright Red Hat
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from oauth2_provider.models import get_refresh_token_model
from oauth2_provider.settings import oauth2_settings

RefreshToken = get_refresh_token_model()


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Do nothing", default=False)

    def handle(self, dry_run, *args, **options):
        print(args)
        min_create_date = timezone.now() - timedelta(
            seconds=oauth2_settings.REFRESH_TOKEN_EXPIRE_SECONDS
        )
        count = RefreshToken.objects.all().filter(created__lt=min_create_date).count()
        self.stdout.write(
            f"Deleting the {count} refreshtoken(s) created before {min_create_date}..."
        )
        if dry_run:
            self.stdout.write("** Doing nothing because of the --dry-run parameter!")
            return
        for refreshtoken in RefreshToken.objects.all().filter(created__lt=min_create_date):
            refreshtoken.revoke()
