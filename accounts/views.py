from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.views.generic import FormView, View
from django.urls import reverse_lazy
from django.contrib import messages
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.conf import settings
from django.http import HttpResponseBadRequest

from accounts.forms import UserRegistrationForm, LoginForm, ResendVerificationEmailForm
from accounts.models import EmailVerificationToken


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
        
        # Send verification email
        self.send_verification_email(user, token)
        
        return super().form_valid(form)
    
    def send_verification_email(self, user, token):
        """Send email verification link to user."""
        verification_url = self.request.build_absolute_uri(
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
            
            # Send verification email
            self.send_verification_email(user, token)
            
            messages.success(self.request, f'Verification email resent to {email}. Please check your email.')
        except User.DoesNotExist:
            messages.error(self.request, 'User not found with this email.')
        
        return super().form_valid(form)
    
    def send_verification_email(self, user, token):
        """Send email verification link to user."""
        verification_url = self.request.build_absolute_uri(
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
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']
        
        user = authenticate(self.request, username=username, password=password)
        
        if user is not None:
            if user.is_active:
                login(self.request, user)
                messages.success(self.request, f'Welcome back, {user.username}!')
                return super().form_valid(form)
            else:
                messages.error(self.request, 'Your account is not activated. Please verify your email.')
                return self.form_invalid(form)
        else:
            messages.error(self.request, 'Invalid username or password.')
            return self.form_invalid(form)


def logout_view(request):
    """User logout."""
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('teams:team_list')
