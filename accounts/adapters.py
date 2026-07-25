from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from accounts.models import EmailVerificationToken


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Activate OAuth users immediately and link to existing accounts by email."""

    def pre_social_login(self, request, sociallogin):
        user = sociallogin.user
        if user and not user.is_active:
            user.is_active = True
            user.save(update_fields=['is_active'])
            EmailVerificationToken.objects.filter(user=user).delete()

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        user.is_active = True
        user.save(update_fields=['is_active'])
        return user
