from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.views.generic import FormView, View, TemplateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.conf import settings
from django.http import HttpResponseBadRequest

from accounts.forms import (
    UserRegistrationForm,
    LoginForm,
    ResendVerificationEmailForm,
    ContactForm,
    ForgotPasswordForm,
    ResetPasswordForm,
)
from accounts.models import EmailVerificationToken, PasswordResetToken
from accounts.services import send_verification_email, send_contact_email, send_password_reset_email
from accounts.allauth_utils import sync_verified_email_address


class RegisterView(FormView):
    """Register a new user with email verification and Turnstile protection."""
    template_name = 'accounts/register.html'
    form_class = UserRegistrationForm
    success_url = reverse_lazy('accounts:registration_pending')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['turnstile_site_key'] = settings.TURNSTILE_SITE_KEY
        return context
    
    def form_valid(self, form):
        # Create inactive user
        user = User.objects.create_user(
            username=form.cleaned_data['username'],
            email=form.cleaned_data['email'],
            password=form.cleaned_data['password'],
            is_active=False  # Inactive until email verified
        )
        
        # Create verification token
        token = EmailVerificationToken.create_for_user(user)
        
        # Send verification email using service
        send_verification_email(self.request, user, token)
        
        return super().form_valid(form)


class VerifyEmailView(View):
    """Verify user email using token."""
    
    def get(self, request, token):
        try:
            verification_token = EmailVerificationToken.objects.get(token=token)
            
            if verification_token.is_expired:
                messages.error(request, 'Verification link has expired. Please register again.')
                return redirect('accounts:register')
            
            # Activate user
            user = verification_token.user
            user.is_active = True
            user.save()
            
            # Keep django-allauth in sync so social login won't wipe the password.
            sync_verified_email_address(user)
            
            # Delete token
            verification_token.delete()
            
            messages.success(request, 'Email verified successfully! You can now log in.')
            return redirect('accounts:login')
        
        except EmailVerificationToken.DoesNotExist:
            return HttpResponseBadRequest('Invalid verification token.')


class RegistrationPendingView(FormView):
    """Show message that registration is pending email verification and allow resending."""
    template_name = 'accounts/registration_pending.html'
    form_class = ResendVerificationEmailForm
    success_url = reverse_lazy('accounts:registration_pending')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['turnstile_site_key'] = settings.TURNSTILE_SITE_KEY
        return context
    
    def form_valid(self, form):
        email = form.cleaned_data['email']
        try:
            user = User.objects.get(email=email)
            # Create new verification token
            token = EmailVerificationToken.create_for_user(user)
            
            # Send verification email using service
            send_verification_email(self.request, user, token)
            
            messages.success(self.request, f'Verification email resent to {email}. Please check your email.')
        except User.DoesNotExist:
            messages.error(self.request, 'User not found with this email.')
        
        return super().form_valid(form)


class LoginView(FormView):
    """User login with Turnstile protection."""
    template_name = 'accounts/login.html'
    form_class = LoginForm
    success_url = reverse_lazy('teams:team_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['turnstile_site_key'] = settings.TURNSTILE_SITE_KEY
        return context

    def form_valid(self, form):
        username_or_email = form.cleaned_data['username']
        password = form.cleaned_data['password']

        user = authenticate(self.request, username=username_or_email, password=password)
        if user is None:
            try:
                existing = User.objects.get(email__iexact=username_or_email)
                user = authenticate(
                    self.request,
                    username=existing.username,
                    password=password,
                )
            except User.DoesNotExist:
                user = None

        if user is not None:
            if user.is_active:
                login(self.request, user)
                messages.success(self.request, f'Welcome back, {user.username}!')
                return super().form_valid(form)
            messages.error(self.request, 'Your account is not activated. Please verify your email.')
            return self.form_invalid(form)

        messages.error(self.request, 'Invalid username or password.')
        return self.form_invalid(form)


class ForgotPasswordView(FormView):
    """Request a password reset link by email."""
    template_name = 'accounts/forgot_password.html'
    form_class = ForgotPasswordForm
    success_url = reverse_lazy('accounts:forgot_password_done')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['turnstile_site_key'] = settings.TURNSTILE_SITE_KEY
        return context

    def form_valid(self, form):
        email = form.cleaned_data['email']
        try:
            user = User.objects.get(email__iexact=email)
            token = PasswordResetToken.create_for_user(user)
            send_password_reset_email(self.request, user, token)
        except User.DoesNotExist:
            pass

        return super().form_valid(form)


class ForgotPasswordDoneView(TemplateView):
    """Confirm that a reset email was sent if the account exists."""
    template_name = 'accounts/forgot_password_done.html'


class ResetPasswordView(FormView):
    """Set a new password using a one-time reset link."""
    template_name = 'accounts/reset_password.html'
    form_class = ResetPasswordForm
    success_url = reverse_lazy('accounts:login')

    def dispatch(self, request, *args, **kwargs):
        try:
            self.reset_token = PasswordResetToken.objects.get(token=kwargs['token'])
        except PasswordResetToken.DoesNotExist:
            messages.error(request, 'Invalid password reset link.')
            return redirect('accounts:forgot_password')

        if self.reset_token.is_expired:
            self.reset_token.delete()
            messages.error(request, 'This password reset link has expired. Please request a new one.')
            return redirect('accounts:forgot_password')

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = self.reset_token.user
        user.set_password(form.cleaned_data['password'])
        user.is_active = True
        user.save()

        sync_verified_email_address(user)
        self.reset_token.delete()

        messages.success(self.request, 'Your password has been reset. You can now log in.')
        return super().form_valid(form)


class ContactView(FormView):
    """Contact form with Turnstile protection."""
    template_name = 'accounts/contact.html'
    form_class = ContactForm
    success_url = reverse_lazy('accounts:contact')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['turnstile_site_key'] = settings.TURNSTILE_SITE_KEY
        return context

    def form_valid(self, form):
        send_contact_email(
            name=form.cleaned_data['name'],
            email=form.cleaned_data['email'],
            subject=form.cleaned_data['subject'],
            message=form.cleaned_data['message'],
        )
        messages.success(self.request, 'Your message has been sent. We will get back to you soon.')
        return super().form_valid(form)


def logout_view(request):
    """User logout."""
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('teams:team_list')
