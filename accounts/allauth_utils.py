from allauth.account.models import EmailAddress


def sync_verified_email_address(user, email=None):
    """
    Mark the user's email as verified in django-allauth.

    Required so allauth does not wipe the password when linking a social account
    to an existing email/password user (see wipe_password in allauth).
    """
    address = (email or user.email or '').strip().lower()
    if not address:
        return

    EmailAddress.objects.update_or_create(
        user=user,
        email=address,
        defaults={'verified': True, 'primary': True},
    )
