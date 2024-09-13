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

from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group
from import_export.admin import ExportMixin

from .models import User

admin.site.unregister(Group)


class MembershipInline(admin.TabularInline):
    model = Group.user_set.through
    extra = 0


@admin.register(User)
class WisdomUserAdmin(ExportMixin, UserAdmin):
    # add any additional fields you want to display in the User page
    list_display = (
        "username",
        "is_staff",
        "uuid",
    )
    search_fields = UserAdmin.search_fields + ("uuid",)


@admin.register(Group)
class WisdomGroupAdmin(GroupAdmin):
    inlines = [MembershipInline]
