from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from import_export import resources
from import_export.admin import ExportMixin

from .models import User


class UserTermsResource(resources.ModelResource):
    class Meta:
        model = User
        fields = ['username', 'date_terms_accepted']
        name = "Export only user terms"


class WisdomUserAdmin(ExportMixin, UserAdmin):
    resource_classes = [UserTermsResource]
    # add any additional fields you want to display in the User page
    list_display = ('username', 'is_staff', 'date_terms_accepted', 'uuid')
    fieldsets = UserAdmin.fieldsets + ((None, {'fields': ('date_terms_accepted',)}),)


admin.site.register(User, WisdomUserAdmin)
