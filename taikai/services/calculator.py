"""Tournament score calculation and standings."""

from django.db.models import Count

from scores.services.calculator import (
    calculate_placement_with_ties,
    calculate_session_score,
    calculate_uma_for_placement,
)
from taikai.models import (
    TournamentMemberTotal,
    TournamentMemberFinalsTotal,
    TournamentSessionScore,
    TournamentMember,
)
from taikai.services.session_generator import is_session_scored


def session_counts_for_finals(session):
    """True when all four seated players are in the finals group."""
    scores = list(session.scores.select_related('member').all())
    if len(scores) != 4:
        return False
    return all(s.member.in_finals for s in scores)


def get_standing_totals(tournament):
    """Return {member_id: {total, games}} for all members (including substitutes)."""
    totals = {}
    for member in tournament.members.all():
        try:
            ts = member.total_score
            totals[member.id] = {'total': ts.total, 'games': ts.games_played}
        except TournamentMemberTotal.DoesNotExist:
            totals[member.id] = {'total': 0.0, 'games': 0}
    return totals


def recalculate_session(session):
    """Assign placements and recalculate totals for session members."""
    scores = list(session.scores.select_related('member').all())
    if len(scores) != 4 or not is_session_scored(session):
        for s in scores:
            s.placement = None
            s.save(update_fields=['placement'])
        tournament = session.tournament
        for s in scores:
            recalculate_member_total(s.member)
            if tournament.finals_cutoff:
                recalculate_member_finals_total(s.member)
        return

    sorted_scores = sorted(scores, key=lambda s: s.score, reverse=True)
    for s in scores:
        s.placement = calculate_placement_with_ties(s.score, sorted_scores)
        s.save(update_fields=['placement'])

    tournament = session.tournament
    for s in scores:
        recalculate_member_total(s.member)
        if tournament.finals_cutoff and session_counts_for_finals(session):
            recalculate_member_finals_total(s.member)


def recalculate_member_total(member):
    """Recompute cached total for one tournament member."""
    tournament = member.tournament
    member_scores = (
        TournamentSessionScore.objects
        .filter(member=member, session__tournament=tournament)
        .select_related('session')
    )

    complete_session_ids = set(
        TournamentSessionScore.objects
        .filter(
            session__tournament=tournament,
            session_id__in=member_scores.values_list('session_id', flat=True),
        )
        .values('session_id')
        .annotate(cnt=Count('id'))
        .filter(cnt=4)
        .values_list('session_id', flat=True)
    )

    total = 0.0
    games = 0
    placements = []
    chombo_total = 0
    placement_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    for ms in member_scores:
        if ms.session_id not in complete_session_ids or ms.placement is None:
            continue
        if not is_session_scored(ms.session):
            continue
        uma = calculate_uma_for_placement(ms.placement, tournament)
        calculated = calculate_session_score(ms.score, ms.placement, uma, tournament, ms.chombo)
        total += calculated
        games += 1
        placements.append(ms.placement)
        placement_rounded = round(ms.placement)
        if 1 <= placement_rounded <= 4:
            placement_counts[placement_rounded] += 1
        if ms.chombo > 0:
            chombo_total += ms.chombo

    obj, _ = TournamentMemberTotal.objects.get_or_create(member=member)
    obj.total = total
    obj.games_played = games
    obj.average_per_game = total / games if games else 0.0
    obj.average_placement = sum(placements) / len(placements) if placements else 0.0
    obj.chombo_count = chombo_total
    obj.first_place_count = placement_counts[1]
    obj.second_place_count = placement_counts[2]
    obj.third_place_count = placement_counts[3]
    obj.fourth_place_count = placement_counts[4]
    obj.save()


def recalculate_member_finals_total(member):
    """Recompute cached finals total from sessions where all four players are in finals."""
    if not member.in_finals:
        TournamentMemberFinalsTotal.objects.filter(member=member).delete()
        return

    tournament = member.tournament
    member_scores = (
        TournamentSessionScore.objects
        .filter(member=member, session__tournament=tournament)
        .select_related('session')
    )

    complete_session_ids = set(
        TournamentSessionScore.objects
        .filter(
            session__tournament=tournament,
            session_id__in=member_scores.values_list('session_id', flat=True),
        )
        .values('session_id')
        .annotate(cnt=Count('id'))
        .filter(cnt=4)
        .values_list('session_id', flat=True)
    )

    total = 0.0
    games = 0
    placements = []
    chombo_total = 0
    placement_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    for ms in member_scores:
        if ms.session_id not in complete_session_ids or ms.placement is None:
            continue
        if not is_session_scored(ms.session):
            continue
        if not session_counts_for_finals(ms.session):
            continue
        uma = calculate_uma_for_placement(ms.placement, tournament)
        calculated = calculate_session_score(ms.score, ms.placement, uma, tournament, ms.chombo)
        total += calculated
        games += 1
        placements.append(ms.placement)
        placement_rounded = round(ms.placement)
        if 1 <= placement_rounded <= 4:
            placement_counts[placement_rounded] += 1
        if ms.chombo > 0:
            chombo_total += ms.chombo

    obj, _ = TournamentMemberFinalsTotal.objects.get_or_create(member=member)
    obj.total = total
    obj.games_played = games
    obj.average_per_game = total / games if games else 0.0
    obj.average_placement = sum(placements) / len(placements) if placements else 0.0
    obj.chombo_count = chombo_total
    obj.first_place_count = placement_counts[1]
    obj.second_place_count = placement_counts[2]
    obj.third_place_count = placement_counts[3]
    obj.fourth_place_count = placement_counts[4]
    obj.save()


def reset_tournament_standings(tournament):
    """Zero out cached standings after sessions are removed or regenerated."""
    for member in tournament.members.all():
        TournamentMemberTotal.objects.update_or_create(
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


def recalculate_tournament(tournament):
    """Recalculate all sessions and member totals."""
    for session in tournament.sessions.all():
        recalculate_session(session)


def get_tournament_standings(tournament):
    """
    Return standing members sorted by total (desc), excluding substitutes.
    Only members with games_played > 0 are included.
    """
    members = (
        tournament.standing_members()
        .select_related('total_score')
        .filter(total_score__games_played__gt=0)
        .order_by('-total_score__total', 'name')
    )
    return list(members)


def get_tournament_finals_standings(tournament):
    """
    Return finals-group members sorted by finals total (desc).
    Only members with finals games_played > 0 are included.
    """
    if not tournament.finals_cutoff:
        return []

    members = (
        tournament.finals_members()
        .select_related('finals_total_score')
        .order_by('-finals_total_score__total', 'name')
    )
    return list(members)


def get_tournament_member_game_history(member):
    """Return chronological game history for a tournament member."""
    tournament = member.tournament
    member_scores = (
        TournamentSessionScore.objects
        .filter(member=member, session__tournament=tournament)
        .select_related('session')
        .order_by('session__order_index', 'session__hanchan_number', 'session__table_number')
    )

    if not member_scores.exists():
        return []

    complete_session_ids = set(
        TournamentSessionScore.objects
        .filter(
            session__tournament=tournament,
            session_id__in=member_scores.values_list('session_id', flat=True),
        )
        .values('session_id')
        .annotate(cnt=Count('id'))
        .filter(cnt=4)
        .values_list('session_id', flat=True)
    )

    game_history = []
    for ms in member_scores:
        if ms.session_id not in complete_session_ids or ms.placement is None:
            continue
        if not is_session_scored(ms.session):
            continue
        uma = calculate_uma_for_placement(ms.placement, tournament)
        calculated = calculate_session_score(ms.score, ms.placement, uma, tournament, ms.chombo)
        game_history.append({
            'session_name': ms.session.name,
            'session_id': ms.session_id,
            'date': ms.session.created_at.date(),
            'raw_score': ms.score,
            'placement': ms.placement,
            'calculated': calculated,
            'chombo': ms.chombo,
        })

    return game_history


def update_session_scores(session, score_data):
    """
    Update roster and scores for a session.
    score_data: list of dicts with member_id, score, chombo (one per seat).
    """
    if len(score_data) != 4:
        raise ValueError('Exactly 4 scores are required per session.')

    member_ids = [entry['member_id'] for entry in score_data]
    if len(set(member_ids)) != 4:
        raise ValueError('Each of the 4 players must be unique.')

    tournament = session.tournament
    valid_ids = set(tournament.members.values_list('id', flat=True))
    if not set(member_ids).issubset(valid_ids):
        raise ValueError('All players must be tournament members.')

    old_member_ids = set(session.scores.values_list('member_id', flat=True))

    session.scores.all().delete()
    for entry in score_data:
        TournamentSessionScore.objects.create(
            session=session,
            member_id=entry['member_id'],
            score=entry['score'],
            chombo=entry.get('chombo', 0) or 0,
        )

    recalculate_session(session)

    for member_id in old_member_ids - set(member_ids):
        recalculate_member_total(TournamentMember.objects.get(pk=member_id))
