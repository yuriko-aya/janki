from django.contrib import admin
from teams.models import Team, Member, Player


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'member_count', 'created_at')
    search_fields = ('name', 'user__username')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('user',)

    @admin.display(description='Teams')
    def member_count(self, obj):
        return obj.members.count()


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'hidden', 'created_at')
    list_filter = ('hidden', 'created_at',)
    search_fields = ('name', 'slug')
    readonly_fields = ('slug', 'created_at', 'updated_at')


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'team', 'player', 'join_date', 'created_at')
    list_filter = ('team', 'join_date')
    search_fields = ('name', 'team__name', 'player__name')
    readonly_fields = ('join_date', 'created_at', 'updated_at')
