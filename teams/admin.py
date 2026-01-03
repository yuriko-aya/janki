from django.contrib import admin
from teams.models import Team, Member


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'hidden', 'created_at')
    list_filter = ('hidden', 'created_at',)
    search_fields = ('name', 'slug')
    readonly_fields = ('slug', 'created_at', 'updated_at')


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'team', 'join_date', 'created_at')
    list_filter = ('team', 'join_date')
    search_fields = ('name', 'team__name')
    readonly_fields = ('join_date', 'created_at', 'updated_at')
