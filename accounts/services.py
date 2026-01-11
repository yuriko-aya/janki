"""
Email and user services for the accounts app.
"""
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.conf import settings


def send_verification_email(request, user, token):
    """
    Send email verification link to user.
    
    Args:
        request: HttpRequest object (for building absolute URI)
        user: User object to send verification email to
        token: EmailVerificationToken object
    """
    verification_url = request.build_absolute_uri(
        reverse_lazy('accounts:verify_email', kwargs={'token': token.token})
    )
    
    subject = 'Verify Your Email - Mahjong Score Tracker'
    html_message = render_to_string('accounts/email_verification.html', {
        'user': user,
        'verification_url': verification_url,
        'timeout_days': settings.ACCOUNT_ACTIVATION_TIMEOUT_DAYS,
    })
    
    send_mail(
        subject,
        f'Please verify your email by visiting: {verification_url}',
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        html_message=html_message,
        fail_silently=False,
    )
