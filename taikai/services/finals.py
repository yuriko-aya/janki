"""Finals cutoff: split top N into a separate standing after qualifier play."""

from django.db import transaction

from taikai.models import Tournament, TournamentMember, TournamentMemberFinalsTotal
from taikai.services.calculator import (
    get_tournament_standings,
    recalculate_member_finals_total,
    session_counts_for_finals,
)
from taikai.services.session_generator import is_hanchan_complete


def can_apply_finals_cutoff(tournament):
    """Return (allowed, message) for applying a finals cutoff."""
    if tournament.finals_cutoff:
        return False, 'Finals cutoff has already been applied.'

    if tournament.session_mode == Tournament.SessionMode.HYBRID:
        for h in range(1, tournament.fixed_hanchan_count + 1):
            if not tournament.sessions.filter(hanchan_number=h).exists():
                return False, 'Generate and score all fixed hanchans before applying cutoff.'
            if not is_hanchan_complete(tournament, h):
                return False, (
                    f'All sessions in fixed Hanchan {h} must be scored (no zero values) '
                    'before applying cutoff.'
                )

    standings = get_tournament_standings(tournament)
    if len(standings) < 4:
        return False, 'At least 4 players with scores are required to apply cutoff.'

    return True, 'Apply cutoff to split the top N into a separate finals standing.'


def clear_finals_cutoff(tournament):
    """Remove finals cutoff state (e.g. when regenerating fixed sessions)."""
    tournament.finals_cutoff = None
    tournament.save(update_fields=['finals_cutoff', 'updated_at'])
    tournament.standing_members().update(in_finals=False)
    TournamentMemberFinalsTotal.objects.filter(member__tournament=tournament).delete()


def reset_finals_standings(tournament):
    """Zero out cached finals totals for all finals-group members."""
    for member in tournament.finals_members():
        TournamentMemberFinalsTotal.objects.update_or_create(
            member=member,
            defaults={
                'total': 0.0,
                'games_played': 0,
                'average_per_game': 0.0,
                'average_placement': 0.0,
                'chombo_count': 0,
                'first_place_count': 0,
                'second_place_count': 0,
                'third_place_count': 0,
                'fourth_place_count': 0,
            },
        )


@transaction.atomic
def apply_finals_cutoff(tournament, cutoff):
    """
    Mark the top `cutoff` players as finals qualifiers and start a separate standing.
    cutoff must be >= 4 and divisible by 4.
    """
    allowed, message = can_apply_finals_cutoff(tournament)
    if not allowed:
        raise ValueError(message)

    if cutoff < 4:
        raise ValueError('Cutoff must be at least 4 players.')
    if cutoff % 4 != 0:
        raise ValueError('Cutoff must be divisible by 4 (tables seat 4 players).')

    standings = get_tournament_standings(tournament)
    if cutoff > len(standings):
        raise ValueError(
            f'Only {len(standings)} player(s) have scores; cutoff cannot exceed that.'
        )

    top_members = standings[:cutoff]
    top_ids = [m.id for m in top_members]

    tournament.finals_cutoff = cutoff
    tournament.save(update_fields=['finals_cutoff', 'updated_at'])

    tournament.standing_members().update(in_finals=False)
    TournamentMember.objects.filter(id__in=top_ids).update(in_finals=True)

    reset_finals_standings(tournament)

    # Re-score any existing all-finals sessions (unlikely before cutoff, but safe).
    for session in tournament.sessions.prefetch_related('scores__member').all():
        if session_counts_for_finals(session):
            for score in session.scores.all():
                recalculate_member_finals_total(score.member)

    return len(top_ids)
