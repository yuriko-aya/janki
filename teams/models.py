from django.db import models
from django.utils.text import slugify


class Team(models.Model):
    """
    A Team represents a group of Mahjong players.
    Each team has exactly one TeamAdmin.
    """
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, db_index=True)
    
    # Scoring configuration
    start_point = models.IntegerField(default=30000, help_text='Starting chips for each player')
    target_point = models.IntegerField(default=30000, help_text='Target score for calculating base points')
    
    # Uma (placement bonus) configuration
    uma_first = models.IntegerField(default=15, help_text='Uma bonus for 1st place')
    uma_second = models.IntegerField(default=5, help_text='Uma bonus for 2nd place')
    uma_third = models.IntegerField(default=-5, help_text='Uma bonus for 3rd place')
    uma_fourth = models.IntegerField(default=-15, help_text='Uma bonus for 4th place')
    
    # Chombo (bankruptcy) configuration
    chombo_enabled = models.BooleanField(default=True, help_text='Enable chombo penalty (-30 points)')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_standings(self):
        """
        Return team members sorted by their calculated score (descending).
        """
        from scores.models import CalculatedScore
        members = self.members.all().prefetch_related('calculated_score')
        # Sort by calculated score total, highest first
        return sorted(
            members,
            key=lambda m: m.calculated_score.total if hasattr(m, 'calculated_score') else 0,
            reverse=True
        )


class Member(models.Model):
    """
    A Member belongs to a Team.
    Each member can submit RawScores for sessions.
    """
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='members', db_index=True)
    name = models.CharField(max_length=100)
    join_date = models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = ['team', 'name']
        indexes = [
            models.Index(fields=['team', 'name']),
        ]

    def __str__(self):
        return f"{self.name} ({self.team.name})"

    def total_score(self):
        """
        Get the calculated score total for this member.
        """
        try:
            return self.calculated_score.total
        except:
            return 0
