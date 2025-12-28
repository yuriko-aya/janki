"""
Management command to recalculate all member scores.
Use this after fixing bugs in the scoring calculation logic.

Usage:
    python manage.py recalculate_scores
    python manage.py recalculate_scores --team=test-team
"""
from django.core.management.base import BaseCommand
from teams.models import Team, Member
from scores.services.calculator import recalculate_member_score


class Command(BaseCommand):
    help = 'Recalculate all member scores (useful after fixing scoring bugs)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--team',
            type=str,
            help='Team slug to recalculate (default: all teams)',
        )

    def handle(self, *args, **options):
        team_slug = options.get('team')
        
        if team_slug:
            try:
                team = Team.objects.get(slug=team_slug)
                teams = [team]
                self.stdout.write(f"Recalculating scores for team: {team.name}")
            except Team.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Team '{team_slug}' not found"))
                return
        else:
            teams = Team.objects.all()
            self.stdout.write(f"Recalculating scores for all {teams.count()} teams")
        
        total_members = 0
        for team in teams:
            members = team.members.all()
            member_count = members.count()
            
            if member_count == 0:
                continue
            
            self.stdout.write(f"\nTeam: {team.name} ({member_count} members)")
            
            for member in members:
                recalculate_member_score(member)
                total_members += 1
                self.stdout.write(f"  ✓ {member.name}")
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ Successfully recalculated scores for {total_members} members"
            )
        )
