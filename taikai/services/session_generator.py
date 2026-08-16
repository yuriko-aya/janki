"""Session completion checks and pairing generation."""

import random
from collections import defaultdict
from itertools import combinations

from django.db import transaction
from django.db.models import Max

from taikai.models import Tournament, TournamentSession, TournamentSessionScore

MAX_SCHEDULE_ATTEMPTS = 500
MINIMIZE_SCHEDULE_ATTEMPTS = 300
MINIMIZE_SCHEDULE_ATTEMPTS_FAST = 100
MINIMIZE_SCHEDULE_ATTEMPTS_CAP = 200
MINIMIZE_SCHEDULE_ATTEMPTS_HARD_CAP = 800


def _max_zero_repeat_hanchans(player_count):
    """Each player meets 3 opponents per hanchan; at most n-1 unique opponents."""
    if player_count < 4:
        return 0
    return (player_count - 1) // 3


def _zero_repeat_schedule_feasible(player_count, hanchan_count):
    return hanchan_count <= _max_zero_repeat_hanchans(player_count)


def _minimize_schedule_attempts(player_count, hanchan_count):
    """Fewer retries when zero-repeat pairings are impossible (greedy converges quickly)."""
    if not _zero_repeat_schedule_feasible(player_count, hanchan_count):
        if hanchan_count >= 20:
            return max(
                MINIMIZE_SCHEDULE_ATTEMPTS_FAST,
                min(MINIMIZE_SCHEDULE_ATTEMPTS_CAP, hanchan_count * 5),
            )
        return max(MINIMIZE_SCHEDULE_ATTEMPTS, hanchan_count * 30)
    return max(MINIMIZE_SCHEDULE_ATTEMPTS, hanchan_count * 30)


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


def _record_pairings(table, pair_counts):
    for i, a in enumerate(table):
        for b in table[i + 1:]:
            key = _pair_key(a.id, b.id)
            pair_counts[key] = pair_counts.get(key, 0) + 1


def _table_is_valid(table, pair_counts):
    """True when no two players at this table have met before."""
    for i, a in enumerate(table):
        for b in table[i + 1:]:
            if pair_counts.get(_pair_key(a.id, b.id), 0) > 0:
                return False
    return True


def _partition_into_tables(remaining, pair_counts):
    """Partition players into tables of 4 without repeat pairings."""
    if not remaining:
        return []
    if len(remaining) < 4:
        return None

    first = remaining[0]
    rest = remaining[1:]
    for others in combinations(rest, 3):
        table = [first] + list(others)
        if _table_is_valid(table, pair_counts):
            rest_after = [m for m in remaining if m not in table]
            sub = _partition_into_tables(rest_after, pair_counts)
            if sub is not None:
                return [table] + sub
    return None


def _pick_table_minimize_repeats(remaining, pair_counts):
    """Build one table, minimizing the highest repeat count at the table."""
    if len(remaining) < 4:
        return remaining[:]

    table = [remaining[0]]
    pool = remaining[1:]
    while len(table) < 4 and pool:
        stats = {}
        for member in pool:
            counts = [pair_counts.get(_pair_key(member.id, t.id), 0) for t in table]
            stats[member.id] = (max(counts), sum(counts))

        min_max = min(stats[m.id][0] for m in pool)
        candidates = [m for m in pool if stats[m.id][0] == min_max]
        min_sum = min(stats[m.id][1] for m in candidates)
        candidates = [m for m in pool if stats[m.id][1] == min_sum]
        choice = random.choice(candidates)
        table.append(choice)
        pool.remove(choice)
    return table


def _chunk_tables(members, pair_counts):
    """Partition one hanchan into tables, avoiding repeat pairings when possible."""
    remaining = list(members)
    random.shuffle(remaining)
    tables = []
    while len(remaining) >= 4:
        table = _pick_table_minimize_repeats(remaining, pair_counts)
        if len(table) < 4:
            break
        for m in table:
            remaining.remove(m)
        _record_pairings(table, pair_counts)
        tables.append(table)
    return tables


def _build_greedy_schedule(members, hanchan_count):
    """Build a full schedule using repeat-minimizing greedy table assignment."""
    pair_counts = defaultdict(int)
    schedule = []
    for _h in range(hanchan_count):
        schedule.append(_chunk_tables(members, pair_counts))
    return schedule, pair_counts


def _schedule_quality(pair_counts):
    if not pair_counts:
        return (0, 0)
    counts = list(pair_counts.values())
    return max(counts), sum(value * value for value in counts)


def _schedule_hanchans_no_repeats(members, hanchan_count):
    """
    Build a full fixed schedule where no two players meet more than once.
    Returns list[hanchan][table][member] or None if not found.
    """
    for _ in range(MAX_SCHEDULE_ATTEMPTS):
        pair_counts = defaultdict(int)
        schedule = []
        for _h in range(hanchan_count):
            order = list(members)
            random.shuffle(order)
            tables = _partition_into_tables(order, pair_counts)
            if not tables:
                break
            for table in tables:
                _record_pairings(table, pair_counts)
            schedule.append(tables)
        else:
            return schedule
    return None


def _target_max_repeat(player_count, hanchan_count):
    """Best possible max repeat count (each player meets 3 opponents per hanchan)."""
    if player_count < 2:
        return 0
    return -(-(3 * hanchan_count) // (player_count - 1))


def _schedule_hanchans_minimize_repeats(members, hanchan_count):
    """Fallback schedule when zero-repeat pairings are impossible."""
    player_count = len(members)
    attempts = _minimize_schedule_attempts(player_count, hanchan_count)
    target_max_repeat = _target_max_repeat(player_count, hanchan_count)
    max_attempts = (
        attempts
        if hanchan_count >= 20
        else min(MINIMIZE_SCHEDULE_ATTEMPTS_HARD_CAP, attempts * 3)
    )
    best_schedule = None
    best_quality = None

    for _ in range(max_attempts):
        schedule, pair_counts = _build_greedy_schedule(members, hanchan_count)
        quality = _schedule_quality(pair_counts)
        if best_quality is None or quality < best_quality:
            best_quality = quality
            best_schedule = schedule
            if quality[0] <= target_max_repeat:
                break

    return best_schedule or _build_greedy_schedule(members, hanchan_count)[0]


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


def _bulk_create_sessions(tournament, schedule, generation_type):
    """Create all sessions and scores in two bulk inserts."""
    session_rows = []
    table_members_list = []
    order_index = 0

    for hanchan_idx, tables in enumerate(schedule, start=1):
        if not tables:
            break
        for table_num, table_members in enumerate(tables, start=1):
            session_rows.append(
                TournamentSession(
                    tournament=tournament,
                    name=f"Hanchan {hanchan_idx} Table {table_num}",
                    hanchan_number=hanchan_idx,
                    table_number=table_num,
                    generation_type=generation_type,
                    order_index=order_index,
                )
            )
            table_members_list.append(table_members)
            order_index += 1

    if not session_rows:
        return 0

    sessions = TournamentSession.objects.bulk_create(session_rows)
    score_rows = []
    for session, table_members in zip(sessions, table_members_list):
        for member in table_members:
            score_rows.append(
                TournamentSessionScore(
                    session=session,
                    member=member,
                    score=0,
                    chombo=0,
                )
            )
    TournamentSessionScore.objects.bulk_create(score_rows)
    return len(sessions)


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
    from taikai.services.finals import clear_finals_cutoff
    reset_tournament_standings(tournament)
    clear_finals_cutoff(tournament)

    player_count = len(members)
    hanchan_count = tournament.fixed_hanchan_count
    if _zero_repeat_schedule_feasible(player_count, hanchan_count):
        schedule = _schedule_hanchans_no_repeats(members, hanchan_count)
    else:
        schedule = None
    if schedule is None:
        schedule = _schedule_hanchans_minimize_repeats(members, hanchan_count)

    sessions_created = _bulk_create_sessions(
        tournament,
        schedule,
        TournamentSession.GenerationType.FIXED,
    )

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
    if tournament.finals_cutoff:
        members = [m for m in members if m.in_finals]
        if len(members) < 4:
            raise ValueError('At least 4 finals players are required to generate rank hanchans.')

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


@transaction.atomic
def create_manual_session(tournament, member_ids):
    """Create one manually assigned session with four selected players."""
    from taikai.models import TournamentMember

    members = list(
        TournamentMember.objects.filter(id__in=member_ids, tournament=tournament)
    )
    if len(members) != 4:
        raise ValueError('Exactly 4 distinct players are required.')

    if tournament.finals_cutoff:
        finals_ids = set(tournament.finals_members().values_list('id', flat=True))
        if not set(member_ids).issubset(finals_ids):
            raise ValueError('All players must be in the finals cutoff group.')

    max_h = _max_hanchan_number(tournament)
    if max_h is None:
        hanchan_number, table_number = 1, 1
    else:
        hanchan_number = max_h
        max_table = (
            tournament.sessions.filter(hanchan_number=hanchan_number)
            .aggregate(m=Max('table_number'))['m']
            or 0
        )
        table_number = max_table + 1

    order_index = _next_order_index(tournament)
    session = _create_session(
        tournament,
        hanchan_number=hanchan_number,
        table_number=table_number,
        generation_type=TournamentSession.GenerationType.MANUAL,
        table_members=members,
        order_index=order_index,
    )
    tournament.sessions_generated = True
    tournament.save(update_fields=['sessions_generated', 'updated_at'])
    return session
