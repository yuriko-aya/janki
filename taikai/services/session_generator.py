"""Session completion checks and pairing generation."""

import random
from collections import defaultdict

from django.db import transaction
from django.db.models import Max

from taikai.models import Tournament, TournamentSession, TournamentSessionScore


def is_session_scored(session):
    """True when all 4 players have a non-zero raw score."""
    scores = list(session.scores.all())
    return len(scores) == 4 and all(s.score != 0 for s in scores)


def is_hanchan_complete(tournament, hanchan_number):
    sessions = tournament.sessions.filter(hanchan_number=hanchan_number)
    if not sessions.exists():
        return False
    return all(is_session_scored(s) for s in sessions)


def _max_hanchan_number(tournament):
    return tournament.sessions.aggregate(m=Max('hanchan_number'))['m']


def _pair_key(a_id, b_id):
    return (min(a_id, b_id), max(a_id, b_id))


def _pick_table_greedy(remaining, pair_counts):
    if len(remaining) < 4:
        return remaining[:]
    table = [remaining[0]]
    pool = remaining[1:]
    while len(table) < 4 and pool:
        best = min(
            pool,
            key=lambda m: sum(pair_counts.get(_pair_key(m.id, t.id), 0) for t in table),
        )
        table.append(best)
        pool.remove(best)
    return table


def _record_pairings(table, pair_counts):
    for i, a in enumerate(table):
        for b in table[i + 1:]:
            key = _pair_key(a.id, b.id)
            pair_counts[key] = pair_counts.get(key, 0) + 1


def _pair_counts_from_fixed_sessions(tournament):
    pair_counts = defaultdict(int)
    for session in tournament.sessions.filter(generation_type=TournamentSession.GenerationType.FIXED):
        members = [s.member for s in session.scores.select_related('member')]
        _record_pairings(members, pair_counts)
    return pair_counts


def _chunk_tables(members, pair_counts):
    remaining = list(members)
    random.shuffle(remaining)
    tables = []
    while len(remaining) >= 4:
        table = _pick_table_greedy(remaining, pair_counts)
        if len(table) < 4:
            break
        for m in table:
            remaining.remove(m)
        _record_pairings(table, pair_counts)
        tables.append(table)
    return tables


def _rank_tables(members, standings):
    def sort_key(member):
        data = standings.get(member.id, {'total': 0.0, 'games': 0})
        return (-data['total'], -data['games'], member.name.lower())

    ordered = sorted(members, key=sort_key)
    tables = []
    for i in range(0, len(ordered) - 3, 4):
        tables.append(ordered[i:i + 4])
    return tables


def _create_session(tournament, hanchan_number, table_number, generation_type, table_members, order_index):
    label = f"Hanchan {hanchan_number} Table {table_number}"
    session = TournamentSession.objects.create(
        tournament=tournament,
        name=label,
        hanchan_number=hanchan_number,
        table_number=table_number,
        generation_type=generation_type,
        order_index=order_index,
    )
    for member in table_members:
        TournamentSessionScore.objects.create(session=session, member=member, score=0, chombo=0)
    return session


def _next_order_index(tournament):
    last = tournament.sessions.order_by('-order_index').first()
    return (last.order_index + 1) if last else 0


@transaction.atomic
def generate_fixed_sessions(tournament):
    """
    Generate all fixed hanchans (fixed + hybrid modes).
    Replaces any existing sessions.
    """
    if tournament.session_mode == Tournament.SessionMode.RANK:
        raise ValueError('Rank-only tournaments do not use bulk fixed generation.')

    members = list(tournament.playing_members())
    if len(members) < 4:
        raise ValueError('At least 4 members are required to generate sessions.')

    tournament.sessions.all().delete()

    from taikai.services.calculator import reset_tournament_standings
    reset_tournament_standings(tournament)

    pair_counts = defaultdict(int)
    order_index = 0
    sessions_created = 0

    for hanchan_idx in range(1, tournament.fixed_hanchan_count + 1):
        tables = _chunk_tables(members, pair_counts)
        if not tables:
            break
        for table_num, table_members in enumerate(tables, start=1):
            _create_session(
                tournament,
                hanchan_number=hanchan_idx,
                table_number=table_num,
                generation_type=TournamentSession.GenerationType.FIXED,
                table_members=table_members,
                order_index=order_index,
            )
            order_index += 1
            sessions_created += 1

    tournament.sessions_generated = sessions_created > 0
    tournament.save(update_fields=['sessions_generated', 'updated_at'])
    return sessions_created


def can_generate_next_rank_hanchan(tournament):
    """Return (allowed, message) for generating the next rank-based hanchan."""
    if tournament.session_mode == Tournament.SessionMode.FIXED:
        return False, 'Fixed-only tournaments do not use rank-based hanchans.'

    if tournament.playing_members().count() < 4:
        return False, 'At least 4 members are required.'

    max_h = _max_hanchan_number(tournament)

    if tournament.session_mode == Tournament.SessionMode.RANK:
        if max_h is None:
            return True, 'Generate the first hanchan (random pairings).'
        if not is_hanchan_complete(tournament, max_h):
            return False, (
                f'All sessions in Hanchan {max_h} must be scored (no zero values) '
                'before generating the next hanchan.'
            )
        return True, f'Generate Hanchan {max_h + 1} (pairings by current standing).'

    # Hybrid: all fixed hanchans must exist and be fully scored first
    if not tournament.sessions.filter(generation_type=TournamentSession.GenerationType.FIXED).exists():
        return False, 'Generate fixed sessions first.'

    for h in range(1, tournament.fixed_hanchan_count + 1):
        if not tournament.sessions.filter(hanchan_number=h).exists():
            return False, 'Generate fixed sessions first.'
        if not is_hanchan_complete(tournament, h):
            return False, (
                f'All sessions in fixed Hanchan {h} must be scored (no zero values) '
                'before generating rank-based hanchans.'
            )

    max_h = _max_hanchan_number(tournament)
    if not tournament.sessions.filter(generation_type=TournamentSession.GenerationType.RANK).exists():
        next_h = tournament.fixed_hanchan_count + 1
        return True, f'Generate first rank hanchan (Hanchan {next_h}, by standing).'

    if not is_hanchan_complete(tournament, max_h):
        return False, (
            f'All sessions in Hanchan {max_h} must be scored (no zero values) '
            'before generating the next hanchan.'
        )
    return True, f'Generate Hanchan {max_h + 1} (pairings by current standing).'


@transaction.atomic
def generate_next_rank_hanchan(tournament):
    """Generate a single rank-based hanchan. Returns number of sessions created."""
    allowed, message = can_generate_next_rank_hanchan(tournament)
    if not allowed:
        raise ValueError(message)

    from taikai.services.calculator import get_standing_totals

    members = list(tournament.playing_members())
    max_h = _max_hanchan_number(tournament)
    order_index = _next_order_index(tournament)

    use_random = (
        tournament.session_mode == Tournament.SessionMode.RANK and max_h is None
    )

    if use_random:
        hanchan_number = 1
        tables = _chunk_tables(members, defaultdict(int))
    elif tournament.session_mode == Tournament.SessionMode.HYBRID and not tournament.sessions.filter(
        generation_type=TournamentSession.GenerationType.RANK
    ).exists():
        hanchan_number = tournament.fixed_hanchan_count + 1
        standings = get_standing_totals(tournament)
        tables = _rank_tables(members, standings)
    else:
        hanchan_number = max_h + 1
        standings = get_standing_totals(tournament)
        tables = _rank_tables(members, standings)

    if not tables:
        raise ValueError('Could not form any tables of 4 players.')

    sessions_created = 0
    for table_num, table_members in enumerate(tables, start=1):
        _create_session(
            tournament,
            hanchan_number=hanchan_number,
            table_number=table_num,
            generation_type=TournamentSession.GenerationType.RANK,
            table_members=table_members,
            order_index=order_index,
        )
        order_index += 1
        sessions_created += 1

    tournament.sessions_generated = True
    tournament.save(update_fields=['sessions_generated', 'updated_at'])
    return sessions_created
