from django.contrib import admin  # noqa

from .models import AIModel


class AIAdmin(admin.ModelAdmin):
    readonly_fields = ('created_at', 'updated_at')


admin.site.register(AIModel, AIAdmin)
