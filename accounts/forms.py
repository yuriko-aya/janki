from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.conf import settings
import requests


class TurnstileWidget(forms.Widget):
    """Custom widget for Cloudflare Turnstile."""
    template_name = 'accounts/turnstile_widget.html'
    
    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['site_key'] = settings.TURNSTILE_SITE_KEY
        return context


class TurnstileMixin:
    """Mixin to validate Turnstile token in forms."""
    
    def clean(self):
        cleaned_data = super().clean()
        token = cleaned_data.get('turnstile_token')
        
        if not token:
            raise ValidationError('Please complete the Turnstile verification.')
        
        # Verify token with Cloudflare
        if not self.verify_turnstile_token(token):
            raise ValidationError('Turnstile verification failed. Please try again.')
        
        return cleaned_data
    
    @staticmethod
    def verify_turnstile_token(token):
        """Verify Turnstile token with Cloudflare API."""
        if not settings.TURNSTILE_SECRET_KEY:
            return True  # Skip verification if secret key not configured
        
        try:
            response = requests.post(
                'https://challenges.cloudflare.com/turnstile/v0/siteverify',
                data={
                    'secret': settings.TURNSTILE_SECRET_KEY,
                    'response': token,
                },
                timeout=5
            )
            data = response.json()
            return data.get('success', False)
        except Exception as e:
            print(f"Turnstile verification error: {e}")
            return False


class UserRegistrationForm(TurnstileMixin, forms.Form):
    """Form for user registration with Turnstile protection."""
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email address'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}),
        min_length=8,
        help_text='Password must be at least 8 characters.'
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm password'}),
        label='Confirm Password'
    )
    turnstile_token = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError('Username already exists. Please choose a different one.')
        return username
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('Email already registered. Please use a different email or log in.')
        return email
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        
        if password and password_confirm:
            if password != password_confirm:
                raise ValidationError('Passwords do not match.')
        
        return cleaned_data


class LoginForm(TurnstileMixin, forms.Form):
    """Form for user login with Turnstile protection."""
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'})
    )
    turnstile_token = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )


class ResendVerificationEmailForm(TurnstileMixin, forms.Form):
    """Form to resend verification email with Turnstile protection."""
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email address'})
    )
    turnstile_token = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        try:
            user = User.objects.get(email=email)
            if user.is_active:
                raise ValidationError('This email is already verified. Please log in.')
        except User.DoesNotExist:
            raise ValidationError('No account found with this email address.')
        return email


class TeamAdminCreationForm(forms.Form):
    """Form for creating a TeamAdmin with a User."""
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError('Username already exists.')
        return username
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('Email already exists.')
        return email
