from django.db import migrations


def fix_tournament_totals(apps, schema_editor):
    from taikai.models import Tournament, TournamentSession
    from taikai.services.calculator import recalculate_tournament

    for session in TournamentSession.objects.all():
        scores = list(session.scores.all())
        if len(scores) != 4 or any(s.score == 0 for s in scores):
            for score in scores:
                score.placement = None
                score.save(update_fields=['placement'])

    for tournament in Tournament.objects.all():
        recalculate_tournament(tournament)


class Migration(migrations.Migration):

    dependencies = [
        ('taikai', '0005_fix_tournament_totals'),
    ]

    operations = [
        migrations.RunPython(fix_tournament_totals, migrations.RunPython.noop),
    ]
