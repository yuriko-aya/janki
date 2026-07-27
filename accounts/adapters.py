from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from accounts.allauth_utils import sync_verified_email_address
from accounts.models import EmailVerificationToken


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Activate OAuth users immediately and link to existing accounts by email."""

    def pre_social_login(self, request, sociallogin):
        user = sociallogin.user
        if not user or not user.pk:
            return

        email = getattr(sociallogin, '_did_authenticate_by_email', None) or user.email

        if not user.is_active:
            user.is_active = True
            user.save(update_fields=['is_active'])
            EmailVerificationToken.objects.filter(user=user).delete()

        # Prevent allauth from wiping the password when linking by email.
        sync_verified_email_address(user, email=email)

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        user.is_active = True
        user.save(update_fields=['is_active'])
        sync_verified_email_address(user)
        return user
