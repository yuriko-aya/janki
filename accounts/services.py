"""
Email and user services for the accounts app.
"""
from django.core.mail import EmailMessage, send_mail
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


def send_password_reset_email(request, user, token):
    """
    Send a one-time password reset link to the user.

    Args:
        request: HttpRequest object (for building absolute URI)
        user: User object to send reset email to
        token: PasswordResetToken object
    """
    reset_url = request.build_absolute_uri(
        reverse_lazy('accounts:reset_password', kwargs={'token': token.token})
    )

    subject = 'Reset Your Password - Mahjong Score Tracker'
    html_message = render_to_string('accounts/email_password_reset.html', {
        'user': user,
        'reset_url': reset_url,
        'timeout_hours': settings.PASSWORD_RESET_TIMEOUT_HOURS,
    })

    send_mail(
        subject,
        f'Reset your password by visiting: {reset_url}',
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        html_message=html_message,
        fail_silently=False,
    )


def send_contact_email(name, email, subject, message):
    """
    Send a contact form submission to the site admin.

    Args:
        name: Sender's name
        email: Sender's email address (used as Reply-To)
        subject: Message subject
        message: Message body
    """
    body = f"From: {name} <{email}>\n\n{message}"
    email_message = EmailMessage(
        subject=f'[Janki Contact] {subject}',
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[settings.CONTACT_EMAIL],
        reply_to=[email],
    )
    email_message.send(fail_silently=False)
