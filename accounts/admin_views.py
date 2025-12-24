"""
Custom Django admin views with Turnstile protection.
"""
from django.contrib import admin
from django.contrib.auth import authenticate, login
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.shortcuts import redirect
from django.conf import settings
from django import forms
from accounts.forms import TurnstileMixin


class AdminLoginForm(TurnstileMixin, forms.Form):
    """Admin login form with Turnstile protection."""
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Username',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password',
        })
    )
    turnstile_token = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )
    
    def __init__(self, request=None, *args, **kwargs):
        """Accept request parameter for compatibility with Django LoginView."""
        self.request = request
        super().__init__(*args, **kwargs)


class AdminLoginView(DjangoLoginView):
    """Custom admin login view with Turnstile protection."""
    form_class = AdminLoginForm
    template_name = 'admin/login.html'
    
    def get_form_kwargs(self):
        """Pass request to form."""
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['turnstile_site_key'] = settings.TURNSTILE_SITE_KEY
        context['site_header'] = self.get_site_header()
        return context
    
    def get_site_header(self):
        """Get the site header from admin site."""
        return admin.site.site_header or 'Django Administration'
    
    def form_valid(self, form):
        """Handle successful form submission."""
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']
        
        user = authenticate(self.request, username=username, password=password)
        
        if user is not None:
            if user.is_staff or user.is_superuser:
                login(self.request, user)
                return redirect(self.get_success_url())
            else:
                form.add_error(None, 'You do not have permission to access the admin.')
                return self.form_invalid(form)
        else:
            form.add_error(None, 'Invalid username or password.')
            return self.form_invalid(form)
