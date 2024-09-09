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

import csv
import datetime
import io
from abc import ABC, abstractmethod
from typing import Optional

from ansible_ai_connect.users.models import User
from ansible_ai_connect.users.serializers import UserResponseSerializer


class BaseGenerator(ABC):

    @staticmethod
    def get_users(
        plan_id: Optional[int] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
    ):
        queryset = (
            User.objects.all().order_by("fk_organization_id").exclude(organization__isnull=True)
        )
        queryset_args = {}
        if plan_id is not None:
            queryset_args["userplan__plan_id"] = plan_id
        if created_after is not None:
            queryset_args["userplan__created_at__gte"] = created_after
        if created_before is not None:
            queryset_args["userplan__created_at__lte"] = created_before

        queryset = queryset.filter(**queryset_args)
        serializer = UserResponseSerializer(queryset, many=True)
        users = serializer.data
        return users

    @abstractmethod
    def generate(
        self,
        plan_id: Optional[int] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
    ):
        pass


class UserTrialsReportGenerator(BaseGenerator):
    """
    Returns a CSV report of user trials.
    """

    def generate(
        self,
        plan_id: Optional[int] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
    ):
        users = BaseGenerator.get_users(plan_id, created_after, created_before)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "OrgId",
                "Org has_api_key",
                "UUID",
                "First name",
                "Last name",
                "Organization name",
                "Plan name",
                "Trial started",
                "Trial expired_at",
            ]
        )
        for user in users:
            organization = user["organization"]
            for plan in user["userplan_set"]:
                row_data = [
                    organization["id"],
                    organization["has_api_key"],
                    user["uuid"],
                    user["given_name"],
                    user["family_name"],
                    organization["name"],
                    plan["plan"]["name"],
                    plan["created_at"],
                    plan["expired_at"],
                ]
                writer.writerow(row_data)

        return output.getvalue()


class UserMarketingReportGenerator(BaseGenerator):
    """
    Returns a CSV report of user marketing preferences.
    """

    def generate(
        self,
        plan_id: Optional[int] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
    ):
        users = BaseGenerator.get_users(plan_id, created_after, created_before)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "OrgId",
                "UUID",
                "First name",
                "Last name",
                "Email",
                "Plan name",
                "Trial started",
                "Trial expired_at",
            ]
        )
        for user in users:
            organization = user["organization"]
            for plan in user.get("userplan_set"):
                if plan["accept_marketing"]:
                    row_data = [
                        organization["id"],
                        user["uuid"],
                        user["given_name"],
                        user["family_name"],
                        user["email"],
                        plan["plan"]["name"],
                        plan["created_at"],
                        plan["expired_at"],
                    ]
                    writer.writerow(row_data)

        return output.getvalue()
