from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Tournament(models.Model):
    """A one-off or short-run tournament (taikai) with pre-generated sessions."""

    class SessionMode(models.TextChoices):
        FIXED = 'fixed', 'Fixed pairings'
        RANK = 'rank', 'Rank-based (Swiss-style)'
        HYBRID = 'hybrid', 'Hybrid (fixed then rank-based)'

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, db_index=True)

    start_point = models.IntegerField(default=30000)
    target_point = models.IntegerField(default=30000)
    uma_first = models.IntegerField(default=15)
    uma_second = models.IntegerField(default=5)
    uma_third = models.IntegerField(default=-5)
    uma_fourth = models.IntegerField(default=-15)
    chombo_enabled = models.BooleanField(default=True)

    session_mode = models.CharField(
        max_length=10,
        choices=SessionMode.choices,
        default=SessionMode.FIXED,
    )
    fixed_hanchan_count = models.PositiveIntegerField(
        default=3,
        help_text='Number of fixed hanchans (used in fixed and hybrid modes only)',
    )

    hidden = models.BooleanField(default=False, db_index=True)
    sessions_generated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def is_admin(self, user):
        if not user or not user.is_authenticated:
            return False
        return self.admins.filter(user=user).exists()

    def playing_members(self):
        """Regular members used for automatic session generation (excludes substitutes)."""
        return self.standing_members()

    def roster_members(self):
        """All members available for manual session roster (includes substitutes)."""
        return self.members.all().order_by('name')

    def standing_members(self):
        """Regular members counted in standings."""
        return self.members.filter(is_substitute=False).order_by('name')

    def uses_fixed_hanchans(self):
        return self.session_mode in (self.SessionMode.FIXED, self.SessionMode.HYBRID)

    def uses_rank_hanchans(self):
        return self.session_mode in (self.SessionMode.RANK, self.SessionMode.HYBRID)


class TournamentAdmin(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tournament_admins')
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='admins')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'tournament']

    def __str__(self):
        return f"{self.user.username} - {self.tournament.name}"


class TournamentMember(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='members')
    player = models.ForeignKey(
        'teams.Player',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tournament_memberships',
    )
    name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=100, blank=True, default='')
    is_substitute = models.BooleanField(
        default=False,
        help_text='Substitutes play in sessions but are excluded from standings',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        unique_together = [['tournament', 'name']]

    @property
    def shown_name(self):
        return self.display_name or self.name

    def __str__(self):
        suffix = ' (sub)' if self.is_substitute else ''
        return f"{self.name}{suffix} ({self.tournament.name})"


class TournamentSession(models.Model):
    class GenerationType(models.TextChoices):
        FIXED = 'fixed', 'Fixed'
        RANK = 'rank', 'Rank-based'

    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='sessions')
    name = models.CharField(max_length=100)
    hanchan_number = models.PositiveIntegerField()
    table_number = models.PositiveIntegerField()
    generation_type = models.CharField(max_length=10, choices=GenerationType.choices)
    order_index = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order_index', 'hanchan_number', 'table_number']
        unique_together = [['tournament', 'name']]

    def __str__(self):
        return f"{self.tournament.name} - {self.name}"

    @property
    def is_scored(self):
        scores = list(self.scores.all())
        return len(scores) == 4 and all(s.score != 0 for s in scores)


class TournamentSessionScore(models.Model):
    session = models.ForeignKey(TournamentSession, on_delete=models.CASCADE, related_name='scores')
    member = models.ForeignKey(TournamentMember, on_delete=models.CASCADE, related_name='session_scores')
    score = models.IntegerField(default=0)
    placement = models.FloatField(null=True, blank=True)
    chombo = models.IntegerField(default=0)

    class Meta:
        unique_together = [['session', 'member']]

    def __str__(self):
        return f"{self.member.name} @ {self.session.name}: {self.score}"


class TournamentMemberTotal(models.Model):
    """Cached standing total for a tournament member."""
    member = models.OneToOneField(TournamentMember, on_delete=models.CASCADE, related_name='total_score')
    total = models.FloatField(default=0.0)
    games_played = models.IntegerField(default=0)
    average_per_game = models.FloatField(default=0.0)
    average_placement = models.FloatField(default=0.0)
    chombo_count = models.IntegerField(default=0)
    first_place_count = models.IntegerField(default=0)
    second_place_count = models.IntegerField(default=0)
    third_place_count = models.IntegerField(default=0)
    fourth_place_count = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.member.name}: {self.total:.1f}"
