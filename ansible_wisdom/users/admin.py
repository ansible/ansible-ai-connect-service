from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group
from import_export import resources
from import_export.admin import ExportMixin

from .models import User

admin.site.unregister(Group)


class MembershipInline(admin.TabularInline):
    model = Group.user_set.through
    extra = 0


class UserTermsResource(resources.ModelResource):
    class Meta:
        model = User
        fields = ['username', 'community_terms_accepted', 'commercial_terms_accepted']
        name = "Export only user terms"


@admin.register(User)
class WisdomUserAdmin(ExportMixin, UserAdmin):
    resource_classes = [UserTermsResource]
    # add any additional fields you want to display in the User page
    list_display = (
        'username',
        'is_staff',
        'community_terms_accepted',
        'commercial_terms_accepted',
        'uuid',
    )
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('community_terms_accepted', 'commercial_terms_accepted')}),
    )


@admin.register(Group)
class WisdomGroupAdmin(GroupAdmin):
    inlines = [MembershipInline]
