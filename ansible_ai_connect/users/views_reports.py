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
import io

from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
)
from rest_framework.generics import RetrieveAPIView
from rest_framework.renderers import BaseRenderer
from rest_framework.response import Response

from ansible_ai_connect.users.models import User

from .permissions import DjangoModelPermissionsWithGET
from .serializers import UserResponseSerializer


class BaseReportView(RetrieveAPIView):
    permission_classes = [DjangoModelPermissionsWithGET]
    pagination_class = None

    def get_queryset(self):
        queryset = User.objects.all().exclude(organization__isnull=True)
        plan_id = self.request.query_params.get("plan_id")
        created_after = self.request.query_params.get("created_after")
        created_before = self.request.query_params.get("created_before")
        if plan_id is not None:
            queryset = queryset.filter(userplan__plan_id=plan_id)
        if created_after is not None:
            queryset = queryset.filter(plans__created_at__gte=created_after)
        if created_before is not None:
            queryset = queryset.filter(plans__created_at__lte=created_before)
        return queryset

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = UserResponseSerializer(queryset, many=True)
        users = serializer.data
        return Response(users)


class UserTrialsReportView(BaseReportView):
    """
    Returns a CSV report of user trials.
    """

    class UserTrialsReportRenderer(BaseRenderer):
        media_type = "text/csv"
        format = "csv"

        def render(self, data, accepted_media_type=None, renderer_context=None):
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(
                ["First name", "Last name", "Organization name", "Plan name", "Trial started"]
            )
            for user in data:
                ams = user.get("ams")
                organization = user.get("organization")
                for plan in user.get("userplan_set"):
                    row_data = [
                        ams.get("first_name"),
                        ams.get("last_name"),
                        organization.get("name"),
                        plan.get("plan").get("name"),
                        plan.get("created_at"),
                    ]
                    writer.writerow(row_data)
            return output.getvalue()

    renderer_classes = [UserTrialsReportRenderer]

    @extend_schema(
        parameters=[
            OpenApiParameter("plan_id", OpenApiTypes.INT, OpenApiParameter.QUERY),
            OpenApiParameter("created_after", OpenApiTypes.DATE, OpenApiParameter.QUERY),
            OpenApiParameter("created_before", OpenApiTypes.DATE, OpenApiParameter.QUERY),
        ],
        responses={
            (200, "text/csv"): {
                "description": "OK",
                "properties": {
                    "First name": {
                        "type": "string",
                    },
                    "Last name": {
                        "type": "string",
                    },
                    "Organization name": {
                        "type": "string",
                    },
                    "Plan name": {
                        "type": "string",
                    },
                    "Trial started": {
                        "type": "string",
                    },
                },
            },
            403: OpenApiResponse(description="Unauthorized"),
        },
        summary="Users trials report",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class UserMarketingReportView(BaseReportView):
    """
    Returns a CSV report of user marketing preferences.
    """

    class UserMarketingReportRenderer(BaseRenderer):
        media_type = "text/csv"
        format = "csv"

        def render(self, data, accepted_media_type=None, renderer_context=None):
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["First name", "Last name", "Email", "Plan name", "Trial started"])
            for user in data:
                ams = user.get("ams")
                for plan in user.get("userplan_set"):
                    if plan.get("accept_marketing"):
                        row_data = [
                            ams.get("first_name"),
                            ams.get("last_name"),
                            ams.get("email"),
                            plan.get("plan").get("name"),
                            plan.get("created_at"),
                        ]
                        writer.writerow(row_data)
            return output.getvalue()

    renderer_classes = [UserMarketingReportRenderer]

    @extend_schema(
        parameters=[
            OpenApiParameter("plan_id", OpenApiTypes.INT, OpenApiParameter.QUERY),
            OpenApiParameter("created_after", OpenApiTypes.DATE, OpenApiParameter.QUERY),
            OpenApiParameter("created_before", OpenApiTypes.DATE, OpenApiParameter.QUERY),
        ],
        responses={
            (200, "text/csv"): {
                "description": "OK",
                "properties": {
                    "First name": {
                        "type": "string",
                    },
                    "Last name": {
                        "type": "string",
                    },
                    "Email": {
                        "type": "string",
                    },
                    "Plan name": {
                        "type": "string",
                    },
                    "Trial started": {
                        "type": "string",
                    },
                },
            },
            403: OpenApiResponse(description="Unauthorized"),
        },
        summary="Users marketing preferences report",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
