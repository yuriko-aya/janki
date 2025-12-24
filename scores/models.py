from django.db import models
from django.core.exceptions import ValidationError


class RawScore(models.Model):
    """
    A RawScore represents a single player's score in one Mahjong session.
    Exactly 4 RawScores should exist per session per team.
    """
    member = models.ForeignKey('teams.Member', on_delete=models.CASCADE, related_name='raw_scores', db_index=True)
    score = models.IntegerField()  # Mahjong score value (e.g., 25000, 18000, etc.)
    placement = models.IntegerField(null=True, blank=True)  # Player position in session (1st, 2nd, 3rd, 4th)
    chombo = models.IntegerField(default=0)  # Number of chombos (bankruptcies) - can be stacked
    session_id = models.CharField(max_length=100, db_index=True)  # Groups 4 scores per session
    session_date = models.DateField(null=True, blank=True)  # Date of the game session (for historical records)
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
        total_score = 0.0
        sessions_participated = set()
        placements = []
        chombo_total = 0
        
        # Get this member's raw scores to know which sessions they participated in
        member_sessions = self.member.raw_scores.values_list('session_id', flat=True).distinct()
        
        # For each session this member participated in
        for session_id in member_sessions:
            # Get ALL raw scores in this session from this team
            session_all_scores = RawScore.objects.filter(
                member__team=self.member.team,
                session_id=session_id
            )
            
            if session_all_scores.count() != 4:
                # Skip incomplete sessions
                continue
            
            sessions_participated.add(session_id)
            
            # Find this member's score in the session
            member_raw_score = session_all_scores.get(member=self.member)
            
            # Sort all scores to determine placement (highest score = 1st place)
            sorted_scores = sorted(session_all_scores, key=lambda x: x.score, reverse=True)
            placement = next(i + 1 for i, s in enumerate(sorted_scores) if s.member == self.member)
            placements.append(placement)
            
            # Get Uma bonus based on placement (using team's uma settings)
            team = self.member.team
            uma_map = {
                1: team.uma_first,
                2: team.uma_second,
                3: team.uma_third,
                4: team.uma_fourth
            }
            uma = uma_map.get(placement, 0)
            
            # Calculate score: (score - target_point) / 1000 + uma
            target = self.member.team.target_point
            calculated = (member_raw_score.score - target) / 1000.0 + uma
            
            # Apply chombo penalty if applicable and enabled for this team
            if member_raw_score.chombo > 0 and team.chombo_enabled:
                calculated -= (30 * member_raw_score.chombo)
                chombo_total += member_raw_score.chombo
            
            total_score += calculated
        
        self.total = total_score
        self.games_played = len(sessions_participated)
        self.average_per_game = self.total / self.games_played if self.games_played > 0 else 0.0
        self.average_placement = sum(placements) / len(placements) if placements else 0.0
        self.chombo_count = chombo_total
