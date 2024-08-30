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

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Initialize the email and names field from the AMS"

    def handle(self, *args, **options):
        cpt = 0
        for user in User.objects.all():
            if user.first_name:
                continue
            ams_data = user.ams()
            if not ams_data:
                continue
            user.given_name = ams_data.get("first_name")
            user.family_name = ams_data.get("last_name")
            user.email = ams_data.get("email")
            user.save()
            cpt += 1

        self.stdout.write(f"{cpt} users migrated.")
