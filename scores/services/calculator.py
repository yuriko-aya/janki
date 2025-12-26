"""
Score calculation and aggregation logic for Mahjong scoring.
Keeps views thin by centralizing business logic here.

Scoring Formula:
  Per game: ((raw_score - target_point) / 1000) + uma + (chombo_penalty if applicable)
  where target_point is configurable per team (default: 30000)
  
  Uma (placement bonus):
    1st place: +15
    2nd place: +5
    3rd place: -5
    4th place: -15
  
  Chombo penalty: -30 (if player went bankrupt)
"""
from django.core.exceptions import ValidationError
from scores.models import RawScore, CalculatedScore


def validate_session_complete(session_id, team):
    """
    Ensure exactly 4 scores exist for this session+team.
    
    Args:
        session_id: The session identifier
        team: The Team object
        
    Raises:
        ValidationError: If the session does not have exactly 4 scores
    """
    count = RawScore.objects.filter(member__team=team, session_id=session_id).count()
    if count != 4:
        raise ValidationError(
            f"Session {session_id} must have exactly 4 scores, found {count}"
        )


def recalculate_member_score(member):
    """
    Recalculate and save the CalculatedScore for a member using Mahjong scoring rules.
    Called after any RawScore is created, updated, or deleted.
    
    Args:
        member: The Member object
    """
    calculated_score, created = CalculatedScore.objects.get_or_create(member=member)
    calculated_score.compute_stats()
    calculated_score.save()


def get_team_standings(team):
    """
    Get all team members with their calculated scores, sorted by total (descending).
    
    Args:
        team: The Team object
        
    Returns:
        QuerySet of Members with calculated scores, sorted by total descending
    """
    members = team.members.select_related('calculated_score').order_by('-calculated_score__total')
    return members


def get_team_standings_by_month(team, month, year):
    """
    Get team members' standings filtered by month/year.
    Calculates scores based only on sessions created in the specified month.
    
    Args:
        team: The Team object
        month: Month number (1-12)
        year: Year number (YYYY)
        
    Returns:
        List of Members with filtered calculated_score, sorted by total descending
    """
    from datetime import datetime
    from django.db.models import Q, F, Sum, Case, When, FloatField, IntegerField
    from django.db.models.functions import ExtractMonth, ExtractYear
    from teams.models import Member
    
    # Get all raw scores for this team in the specified month/year
    monthly_raw_scores = RawScore.objects.filter(
        member__team=team,
        created_at__year=year,
        created_at__month=month
    )
    
    # If no scores in this month, return all members with 0 scores
    if not monthly_raw_scores.exists():
        members = team.members.all()
        for member in members:
            # Create a temporary object with zero stats
            member.monthly_total = 0.0
            member.monthly_games = 0
            member.monthly_average = 0.0
        return sorted(members, key=lambda m: m.monthly_total, reverse=True)
    
    # Group scores by session to identify complete sessions
    sessions = {}
    for raw_score in monthly_raw_scores:
        if raw_score.session_id not in sessions:
            sessions[raw_score.session_id] = []
        sessions[raw_score.session_id].append(raw_score)
    
    # Calculate scores per member based on complete sessions only
    member_scores = {}
    for session_id, session_scores in sessions.items():
        if len(session_scores) != 4:
            # Skip incomplete sessions
            continue
        
        for raw_score in session_scores:
            if raw_score.member_id not in member_scores:
                member_scores[raw_score.member_id] = {
                    'total': 0.0,
                    'games': 0,
                    'placements': [],
                    'chombo_count': 0,
                    'first_place': 0,
                    'second_place': 0,
                    'third_place': 0,
                    'fourth_place': 0
                }
            
            # Sort all scores in session to determine placement
            sorted_scores = sorted(session_scores, key=lambda x: x.score, reverse=True)
            
            # Handle ties: find all players with the same score
            member_score_value = raw_score.score
            tied_players = [s for s in sorted_scores if s.score == member_score_value]
            
            # Calculate placement for ties
            if len(tied_players) > 1:
                # Multiple players tied - calculate shared placement
                first_tied_idx = next(i for i, s in enumerate(sorted_scores) if s.score == member_score_value)
                # Shared placement is average of positions (e.g., tied for 1st-2nd = 1.5)
                placement = sum(range(first_tied_idx + 1, first_tied_idx + len(tied_players) + 1)) / len(tied_players)
            else:
                # No tie - normal placement
                placement = next(i + 1 for i, s in enumerate(sorted_scores) if s.member_id == raw_score.member_id)
            
            # Calculate score: (score - target_point) / 1000 + uma (using team's uma settings)
            uma_map = {
                1: team.uma_first,
                2: team.uma_second,
                3: team.uma_third,
                4: team.uma_fourth
            }
            
            # For ties, calculate shared Uma by averaging the tied positions' Uma values
            if len(tied_players) > 1:
                first_tied_idx = next(i for i, s in enumerate(sorted_scores) if s.score == member_score_value)
                tied_positions = range(first_tied_idx + 1, first_tied_idx + len(tied_players) + 1)
                uma = sum(uma_map.get(pos, 0) for pos in tied_positions) / len(tied_players)
            else:
                uma = uma_map.get(int(placement), 0)
            
            calculated = (raw_score.score - team.target_point) / 1000.0 + uma
            
            # Apply chombo penalty if enabled for this team
            if raw_score.chombo > 0 and team.chombo_enabled:
                calculated -= (30 * raw_score.chombo)
                member_scores[raw_score.member_id]['chombo_count'] += raw_score.chombo
            
            member_scores[raw_score.member_id]['total'] += calculated
            member_scores[raw_score.member_id]['games'] += 1
            member_scores[raw_score.member_id]['placements'].append(placement)
            
            # Count placements (round fractional placements to nearest integer for statistics)
            placement_rounded = round(placement)
            if placement_rounded == 1:
                member_scores[raw_score.member_id]['first_place'] += 1
            elif placement_rounded == 2:
                member_scores[raw_score.member_id]['second_place'] += 1
            elif placement_rounded == 3:
                member_scores[raw_score.member_id]['third_place'] += 1
            elif placement_rounded == 4:
                member_scores[raw_score.member_id]['fourth_place'] += 1
    
    # Attach calculated scores to members
    members = team.members.all()
    for member in members:
        if member.id in member_scores:
            member.monthly_total = member_scores[member.id]['total']
            member.monthly_games = member_scores[member.id]['games']
            member.monthly_average = member.monthly_total / member.monthly_games if member.monthly_games > 0 else 0.0
            placements = member_scores[member.id]['placements']
            member.monthly_avg_placement = sum(placements) / len(placements) if placements else 0.0
            member.monthly_chombo_count = member_scores[member.id]['chombo_count']
            member.monthly_first_place = member_scores[member.id]['first_place']
            member.monthly_second_place = member_scores[member.id]['second_place']
            member.monthly_third_place = member_scores[member.id]['third_place']
            member.monthly_fourth_place = member_scores[member.id]['fourth_place']
        else:
            member.monthly_total = 0.0
            member.monthly_games = 0
            member.monthly_average = 0.0
            member.monthly_avg_placement = 0.0
            member.monthly_chombo_count = 0
            member.monthly_first_place = 0
            member.monthly_second_place = 0
            member.monthly_third_place = 0
            member.monthly_fourth_place = 0
    
    # Sort by monthly total
    return sorted(members, key=lambda m: m.monthly_total, reverse=True)


def submit_session_scores(session_id, team, score_data, session_date=None):
    """
    Submit all scores for a session at once.
    Validates that exactly 4 scores are provided.
    
    Args:
        session_id: The session identifier
        team: The Team object
        score_data: List of dicts with {'member_id': int, 'score': int, 'chombo': bool}
        session_date: Optional date of the session (for historical records)
        
    Returns:
        List of created RawScore objects
        
    Raises:
        ValidationError: If validation fails
    """
    if len(score_data) != 4:
        raise ValidationError(f"Expected 4 scores, got {len(score_data)}")
    
    raw_scores = []
    for data in score_data:
        member_id = data.get('member_id')
        score = data.get('score')
        chombo = data.get('chombo', 0)
        
        if member_id is None or score is None:
            raise ValidationError("Each score entry must have member_id and score")
        
        # Verify member belongs to the team
        from teams.models import Member
        try:
            member = Member.objects.get(id=member_id, team=team)
        except Member.DoesNotExist:
            raise ValidationError(f"Member {member_id} does not belong to team {team.id}")
        
        # Create RawScore (placement will be set later)
        raw_score = RawScore(
            member=member,
            score=int(score),
            chombo=int(chombo),
            session_id=session_id,
            session_date=session_date
        )
        raw_score.full_clean()
        raw_scores.append(raw_score)
    
    # Sort scores by score value (descending) to determine placement
    sorted_raw_scores = sorted(raw_scores, key=lambda x: x.score, reverse=True)
    
    # Assign placements, handling ties
    for i, raw_score in enumerate(sorted_raw_scores):
        # Find all scores with same value
        score_value = raw_score.score
        tied_scores = [s for s in sorted_raw_scores if s.score == score_value]
        
        if len(tied_scores) > 1:
            # Calculate shared placement for tied players
            first_tied_idx = next(idx for idx, s in enumerate(sorted_raw_scores) if s.score == score_value)
            shared_placement = sum(range(first_tied_idx + 1, first_tied_idx + len(tied_scores) + 1)) / len(tied_scores)
            raw_score.placement = shared_placement
        else:
            # No tie - normal placement
            raw_score.placement = i + 1
    
    # Bulk create all scores
    RawScore.objects.bulk_create(raw_scores)
    
    # Recalculate all affected members
    for raw_score in raw_scores:
        recalculate_member_score(raw_score.member)
    
    return raw_scores


def update_session_scores(session_id, team, score_data, session_date=None):
    """
    Update all scores for an existing session.
    Deletes old scores and creates new ones.
    
    Args:
        session_id: The session identifier
        team: The Team object
        score_data: List of dicts with {'member_id': int, 'score': int, 'chombo': bool}
        session_date: Optional date of the session (for historical records)
        
    Returns:
        List of created RawScore objects
        
    Raises:
        ValidationError: If validation fails
    """
    # Get all members affected (before and after the update)
    old_scores = RawScore.objects.filter(member__team=team, session_id=session_id)
    affected_members = set(score.member for score in old_scores)
    
    # Delete existing scores for this session
    old_scores.delete()
    
    # Create new scores using the submit function
    new_scores = submit_session_scores(session_id, team, score_data, session_date)
    
    # Add new members to affected set
    for score in new_scores:
        affected_members.add(score.member)
    
    # Recalculate all affected members
    for member in affected_members:
        recalculate_member_score(member)
    
    return new_scores


def get_session_details(session_id, team):
    """
    Get detailed scoring information for a session.
    
    Args:
        session_id: The session identifier
        team: The Team object
        
    Returns:
        Dict with session details including placement and calculated scores
    """
    raw_scores = RawScore.objects.filter(
        member__team=team, 
        session_id=session_id
    ).select_related('member').order_by('placement')
    
    if raw_scores.count() != 4:
        return None
    
    session_details = {
        'session_id': session_id,
        'players': []
    }
    
    # Calculate scores for each player
    for raw_score in raw_scores:
        # Use stored placement or calculate it from score ranking
        if raw_score.placement:
            placement = raw_score.placement
        else:
            # Fallback: calculate from score ranking if placement not stored
            all_session_scores = list(raw_scores)
            sorted_scores = sorted(all_session_scores, key=lambda x: x.score, reverse=True)
            
            # Handle ties
            score_value = raw_score.score
            tied_scores = [s for s in sorted_scores if s.score == score_value]
            
            if len(tied_scores) > 1:
                # Calculate shared placement for tied players
                first_tied_idx = next(i for i, s in enumerate(sorted_scores) if s.score == score_value)
                placement = sum(range(first_tied_idx + 1, first_tied_idx + len(tied_scores) + 1)) / len(tied_scores)
            else:
                # No tie - normal placement
                placement = next(i + 1 for i, s in enumerate(sorted_scores) if s.id == raw_score.id)
        
        # Use team's uma configuration
        uma_map = {
            1: team.uma_first,
            2: team.uma_second,
            3: team.uma_third,
            4: team.uma_fourth
        }
        
        # For ties, calculate shared Uma by averaging the tied positions' Uma values
        all_session_scores = list(raw_scores)
        sorted_scores = sorted(all_session_scores, key=lambda x: x.score, reverse=True)
        score_value = raw_score.score
        tied_scores = [s for s in sorted_scores if s.score == score_value]
        
        if len(tied_scores) > 1:
            first_tied_idx = next(i for i, s in enumerate(sorted_scores) if s.score == score_value)
            tied_positions = range(first_tied_idx + 1, first_tied_idx + len(tied_scores) + 1)
            uma = sum(uma_map.get(pos, 0) for pos in tied_positions) / len(tied_scores)
        else:
            uma = uma_map.get(int(placement), 0)
        
        # Calculate score: (score - target_point) / 1000 + uma
        base_score = (raw_score.score - team.target_point) / 1000.0
        calculated = base_score + uma
        
        # Apply chombo penalty if enabled for this team
        if raw_score.chombo and team.chombo_enabled:
            calculated -= 30
        
        session_details['players'].append({
            'member': raw_score.member.name,
            'placement': placement,
            'raw_score': raw_score.score,
            'base_score': base_score,
            'uma': uma,
            'chombo': raw_score.chombo,
            'calculated_score': calculated
        })
    
    return session_details
