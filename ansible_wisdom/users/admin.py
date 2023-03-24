from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


class WisdomUserAdmin(UserAdmin):
    # add any additional fields you want to display in the User page
    list_display = ('username', 'is_staff', 'date_terms_accepted', 'uuid')
    fieldsets = UserAdmin.fieldsets + ((None, {'fields': ('date_terms_accepted',)}),)


admin.site.register(User, WisdomUserAdmin)
