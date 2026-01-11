from django.db import models
from django.core.exceptions import ValidationError


class RawScore(models.Model):
    """
    A RawScore represents a single player's score in one Mahjong session.
    Exactly 4 RawScores should exist per session per team.
    """
    member = models.ForeignKey('teams.Member', on_delete=models.CASCADE, related_name='raw_scores', db_index=True)
    score = models.IntegerField()  # Mahjong score value (e.g., 25000, 18000, etc.)
    placement = models.FloatField(null=True, blank=True)  # Player position in session (1-4, can be fractional for ties like 1.5)
    chombo = models.IntegerField(default=0)  # Number of chombos (bankruptcies) - can be stacked
    session_id = models.CharField(max_length=100, db_index=True)  # Groups 4 scores per session
    session_date = models.DateField(null=True, blank=True)  # Date of the game session (for historical records)
    archived = models.BooleanField(default=False, db_index=True)  # Archived scores are excluded from standings
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['member', 'session_id']
        indexes = [
            models.Index(fields=['member', 'session_id']),
            models.Index(fields=['session_id']),
        ]

    def __str__(self):
        chombo_str = f" ({self.chombo}x CHOMBO)" if self.chombo > 0 else ""
        return f"{self.member.name} - Session {self.session_id}: {self.score}{chombo_str}"

    def clean(self):
        """Validate that this member is not already in the session."""
        existing = RawScore.objects.filter(
            member__team=self.member.team,
            session_id=self.session_id,
            member=self.member
        ).exclude(pk=self.pk)
        if existing.exists():
            raise ValidationError(
                f"Member {self.member.name} already has a score in session {self.session_id}"
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
        # Recalculate the member's total score after saving
        from scores.services.calculator import recalculate_member_score
        recalculate_member_score(self.member)


class CalculatedScore(models.Model):
    """
    CalculatedScore stores the aggregated total for a Member using Mahjong scoring rules.
    This is precomputed and updated whenever RawScores change.
    
    Scoring Formula (Mahjong):
    - Base: (raw_score - target_point) / 1000  (target_point is configurable per team, default 30000)
    - Uma: Placement bonus (configurable per team, defaults: +15, +5, -5, -15)
    - Chombo: -30 if bankrupt (configurable per team)
    - Calculated = Base + Uma + Chombo_penalty
    """
    member = models.OneToOneField('teams.Member', on_delete=models.CASCADE, related_name='calculated_score')
    total = models.FloatField(default=0.0)  # Sum of all calculated scores
    games_played = models.IntegerField(default=0)  # Number of sessions played
    average_per_game = models.FloatField(default=0.0)  # Average score per game
    average_placement = models.FloatField(default=0.0)  # Average placement (1st-4th)
    chombo_count = models.IntegerField(default=0)  # Total number of chombos
    first_place_count = models.IntegerField(default=0)  # Number of 1st place finishes
    second_place_count = models.IntegerField(default=0)  # Number of 2nd place finishes
    third_place_count = models.IntegerField(default=0)  # Number of 3rd place finishes
    fourth_place_count = models.IntegerField(default=0)  # Number of 4th place finishes
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Calculated Score'
        verbose_name_plural = 'Calculated Scores'

    def __str__(self):
        return f"{self.member.name} - Total: {self.total:.1f}"

    def compute_stats(self):
        """
        Recompute total, games_played, and average_per_game using Mahjong scoring rules.
        Called by the calculator service.
        
        Formula per session:
        1. Get all 4 raw scores for the session from ALL team members
        2. Determine placement (1-4) by sorting session scores
        3. For this member: ((score - target_point) / 1000) + uma + (chombo_penalty if applicable)
           where target_point is team.target_point (default 30000)
        4. Sum calculated scores across all complete sessions
        """
        from scores.services.calculator import (
            calculate_placement_with_ties,
            calculate_uma_for_placement,
            calculate_session_score
        )
        
        total_score = 0.0
        sessions_participated = set()
        placements = []
        chombo_total = 0
        placement_counts = {1: 0, 2: 0, 3: 0, 4: 0}
        
        # Get this member's raw scores to know which sessions they participated in (exclude archived)
        member_sessions = self.member.raw_scores.filter(archived=False).values_list('session_id', flat=True).distinct()
        
        # For each session this member participated in
        for session_id in member_sessions:
            # Get ALL raw scores in this session from this team (exclude archived)
            session_all_scores = RawScore.objects.filter(
                member__team=self.member.team,
                session_id=session_id,
                archived=False
            )
            
            if session_all_scores.count() != 4:
                # Skip incomplete sessions
                continue
            
            sessions_participated.add(session_id)
            
            # Find this member's score in the session
            member_raw_score = session_all_scores.get(member=self.member)
            
            # Sort all scores to determine placement (highest score = 1st place)
            sorted_scores = sorted(list(session_all_scores), key=lambda x: x.score, reverse=True)
            
            # Use helper function to calculate placement with tie handling
            placement = calculate_placement_with_ties(member_raw_score.score, sorted_scores)
            placements.append(placement)
            
            # Count discrete placements for statistics (round to nearest integer)
            placement_rounded = round(placement)
            if 1 <= placement_rounded <= 4:
                placement_counts[placement_rounded] += 1
            
            # Use helper function to get Uma bonus
            uma = calculate_uma_for_placement(placement, self.member.team)
            
            # Use helper function to calculate final score with chombo
            calculated = calculate_session_score(
                member_raw_score.score,
                placement,
                uma,
                self.member.team,
                member_raw_score.chombo
            )
            
            # Track chombo count
            if member_raw_score.chombo > 0:
                chombo_total += member_raw_score.chombo
            
            total_score += calculated
        
        self.total = total_score
        self.games_played = len(sessions_participated)
        self.average_per_game = self.total / self.games_played if self.games_played > 0 else 0.0
        self.average_placement = sum(placements) / len(placements) if placements else 0.0
        self.chombo_count = chombo_total
        self.first_place_count = placement_counts[1]
        self.second_place_count = placement_counts[2]
        self.third_place_count = placement_counts[3]
        self.fourth_place_count = placement_counts[4]
