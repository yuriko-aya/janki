from django.contrib import admin

from taikai.models import (
    Tournament,
    TournamentAdmin,
    TournamentMember,
    TournamentSession,
    TournamentSessionScore,
    TournamentMemberTotal,
    TournamentMemberFinalsTotal,
)


@admin.register(Tournament)
class TournamentAdminModel(admin.ModelAdmin):
    list_display = ('name', 'slug', 'session_mode', 'sessions_generated', 'hidden', 'created_at')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


admin.site.register(TournamentAdmin)
admin.site.register(TournamentMember)
admin.site.register(TournamentSession)
admin.site.register(TournamentSessionScore)
admin.site.register(TournamentMemberTotal)
admin.site.register(TournamentMemberFinalsTotal)
