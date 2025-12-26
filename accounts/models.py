from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import secrets


class TeamAdmin(models.Model):
    """
    TeamAdmin links a User to a Team.
    A user can be admin of multiple teams.
    A team can have multiple admins.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='team_admins')
    team = models.ForeignKey('teams.Team', on_delete=models.CASCADE, related_name='admins')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Team Admin'
        verbose_name_plural = 'Team Admins'
        unique_together = ['user', 'team']  # Prevent duplicate admin entries

    def __str__(self):
        return f"{self.user.username} - {self.team.name}"


class EmailVerificationToken(models.Model):
    """
    Token for email verification during registration.
    Tokens expire after ACCOUNT_ACTIVATION_TIMEOUT_DAYS.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='verification_token')
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Email Verification Token'
        verbose_name_plural = 'Email Verification Tokens'
    
    def __str__(self):
        return f"Token for {self.user.username}"
    
    @property
    def is_expired(self):
        """Check if token has expired (default: 7 days)."""
        from django.conf import settings
        timeout_days = getattr(settings, 'ACCOUNT_ACTIVATION_TIMEOUT_DAYS', 7)
        expiry_date = self.created_at + timedelta(days=timeout_days)
        return timezone.now() > expiry_date
    
    @staticmethod
    def generate_token():
        """Generate a secure random token."""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def create_for_user(user):
        """Create a verification token for a user."""
        # Delete any existing token
        EmailVerificationToken.objects.filter(user=user).delete()
        # Create new token
        token = EmailVerificationToken.objects.create(
            user=user,
            token=EmailVerificationToken.generate_token()
        )
        return token
