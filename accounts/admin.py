from django.contrib import admin
from accounts.models import TeamAdmin


@admin.register(TeamAdmin)
class TeamAdminAdmin(admin.ModelAdmin):
    list_display = ('user', 'team', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'team__name')
    readonly_fields = ('created_at',)
