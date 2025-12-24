from django.contrib import admin
from scores.models import RawScore, CalculatedScore

# Import API admin configuration
from scores import api_admin


@admin.register(RawScore)
class RawScoreAdmin(admin.ModelAdmin):
    list_display = ('member', 'score', 'session_id', 'created_at')
    list_filter = ('created_at', 'member__team')
    search_fields = ('member__name', 'session_id')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)


@admin.register(CalculatedScore)
class CalculatedScoreAdmin(admin.ModelAdmin):
    list_display = ('member', 'total', 'games_played', 'average_per_game', 'updated_at')
    list_filter = ('updated_at', 'member__team')
    search_fields = ('member__name', 'member__team__name')
    readonly_fields = ('updated_at', 'total', 'games_played', 'average_per_game')
