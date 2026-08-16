"""Backfill finals_start_order_index and recalculate finals standings."""

from django.db import migrations
from django.db.models import Max


def backfill_finals_start_order_index(apps, schema_editor):
    Tournament = apps.get_model('taikai', 'Tournament')
    TournamentSession = apps.get_model('taikai', 'TournamentSession')

    for tournament in Tournament.objects.filter(
        finals_cutoff__isnull=False,
        finals_start_order_index__isnull=True,
    ):
        if tournament.session_mode == 'hybrid':
            max_order = (
                TournamentSession.objects.filter(
                    tournament_id=tournament.id,
                    hanchan_number__lte=tournament.fixed_hanchan_count,
                ).aggregate(m=Max('order_index'))['m']
            )
        else:
            max_order = (
                TournamentSession.objects.filter(tournament_id=tournament.id)
                .aggregate(m=Max('order_index'))['m']
            )
        tournament.finals_start_order_index = max_order if max_order is not None else -1
        tournament.save(update_fields=['finals_start_order_index'])

    # Recalculate finals totals using current rules (post-cutoff sessions only).
    from taikai.models import Tournament as LiveTournament
    from taikai.services.calculator import recalculate_tournament_finals_standings

    for tournament in LiveTournament.objects.filter(finals_cutoff__isnull=False):
        recalculate_tournament_finals_standings(tournament)


class Migration(migrations.Migration):

    dependencies = [
        ('taikai', '0009_finals_start_order_index'),
    ]

    operations = [
        migrations.RunPython(backfill_finals_start_order_index, migrations.RunPython.noop),
    ]
