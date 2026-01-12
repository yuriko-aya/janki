from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.models import User
from django.views import View
from django.conf import settings
from drf_multitokenauth.models import MultiToken
import base64
import json
from hashlib import sha256
from cryptography.fernet import Fernet, InvalidToken
from teams.models import Team, Member
from teams.forms import TeamForm, MemberForm, AddTeamAdminForm
from teams.mixins import TeamAdminRequiredMixin, TeamSlugMixin, TeamContextMixin
from accounts.models import TeamAdmin
from scores.services.calculator import get_team_standings, get_inactive_members
from scores.export_utils import export_standings_to_csv, export_standings_to_pdf


class TeamListView(ListView):
    """List all teams (public view - no auth required)."""
    model = Team
    template_name = 'teams/team_list.html'
    context_object_name = 'teams'
    paginate_by = 20
    
    def get_queryset(self):
        # Show all public teams, plus hidden teams where user is admin
        queryset = Team.objects.filter(hidden=False)
        
        if self.request.user.is_authenticated:
            # Include hidden teams where user is admin
            admin_team_ids = TeamAdmin.objects.filter(user=self.request.user).values_list('team_id', flat=True)
            hidden_admin_teams = Team.objects.filter(id__in=admin_team_ids, hidden=True)
            queryset = queryset | hidden_admin_teams
        
        return queryset.distinct().order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            # Get list of team IDs where user is admin
            admin_team_ids = TeamAdmin.objects.filter(user=self.request.user).values_list('team_id', flat=True)
            context['user_admin_team_ids'] = list(admin_team_ids)
        else:
            context['user_admin_team_ids'] = []
        return context


class TeamDetailView(TeamSlugMixin, TeamContextMixin, DetailView):
    """Display team details and standings (public view - no auth required)."""
    model = Team
    template_name = 'teams/team_detail.html'
    context_object_name = 'team'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get standings sorted by calculated score
        context['standings'] = get_team_standings(self.team)
        context['inactive_members'] = get_inactive_members(self.team)
        return context


class TeamCreateView(LoginRequiredMixin, CreateView):
    """Create a new team (admin-only - creates TeamAdmin link)."""
    model = Team
    form_class = TeamForm
    template_name = 'teams/team_form.html'
    success_url = reverse_lazy('teams:team_list')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        # Create TeamAdmin link for the creator
        TeamAdmin.objects.create(user=self.request.user, team=self.object)
        return response


class TeamUpdateView(TeamAdminRequiredMixin, UpdateView):
    """Update a team (admin-only - checks user is team admin)."""
    model = Team
    form_class = TeamForm
    template_name = 'teams/team_form.html'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    
    def get_success_url(self):
        return reverse_lazy('teams:team_detail', kwargs={'slug': self.object.slug})


class MemberListView(TeamAdminRequiredMixin, DetailView):
    """Display all members of a team (admin view)."""
    model = Team
    template_name = 'teams/member_list.html'
    context_object_name = 'team'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'


class MemberCreateView(TeamAdminRequiredMixin, TeamContextMixin, CreateView):
    """Add a new member to a team (admin-only)."""
    model = Member
    form_class = MemberForm
    template_name = 'teams/member_form.html'
    
    def form_valid(self, form):
        member = form.save(commit=False)
        member.team = self.team
        member.save()
        return redirect('teams:member_list', slug=self.team.slug)


class MemberUpdateView(LoginRequiredMixin, UpdateView):
    """Update a team member (admin-only)."""
    model = Member
    form_class = MemberForm
    template_name = 'teams/member_form.html'
    
    def dispatch(self, request, *args, **kwargs):
        member = self.get_object()
        self.team_slug = member.team.slug
        if not member.team.is_admin(request.user):
            raise PermissionDenied("You do not have permission to manage this member.")
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['team'] = self.get_object().team
        return context
    
    def get_success_url(self):
        return reverse_lazy('teams:member_list', kwargs={'slug': self.team_slug})


class MemberDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a team member (admin-only)."""
    model = Member
    template_name = 'teams/member_confirm_delete.html'
    
    def dispatch(self, request, *args, **kwargs):
        member = self.get_object()
        self.team_slug = member.team.slug
        if not member.team.is_admin(request.user):
            raise PermissionDenied("You do not have permission to manage this member.")
        return super().dispatch(request, *args, **kwargs)
    
    def get_success_url(self):
        return reverse_lazy('teams:member_list', kwargs={'slug': self.team_slug})


class TeamAdminListView(TeamAdminRequiredMixin, DetailView):
    """Display all admins of a team and allow adding/removing admins."""
    model = Team
    template_name = 'teams/team_admin_list.html'
    context_object_name = 'team'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['team_admins'] = self.team.admins.all().select_related('user')
        context['form'] = AddTeamAdminForm(team=self.team)
        return context


class AddTeamAdminView(TeamAdminRequiredMixin, FormView):
    """Add a new admin to a team."""
    form_class = AddTeamAdminForm
    template_name = 'teams/team_admin_list.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['team'] = self.team
        return kwargs
    
    def form_valid(self, form):
        username = form.cleaned_data['username']
        user = User.objects.get(username=username)
        
        TeamAdmin.objects.create(team=self.team, user=user)
        messages.success(self.request, f"User '{username}' has been added as a team admin.")
        return redirect('teams:admin_list', slug=self.team.slug)
    
    def form_invalid(self, form):
        messages.error(self.request, "Error adding admin. Please check the form.")
        return redirect('teams:admin_list', slug=self.team.slug)


class RemoveTeamAdminView(LoginRequiredMixin, DeleteView):
    """Remove an admin from a team."""
    model = TeamAdmin
    template_name = 'teams/team_admin_confirm_delete.html'
    
    def dispatch(self, request, *args, **kwargs):
        team_admin = self.get_object()
        team = team_admin.team
        
        # Check if user is an admin of this team
        if not team.is_admin(request.user):
            raise PermissionDenied("You do not have permission to manage this team.")
        
        # Prevent removing the last admin
        if team.admins.count() <= 1:
            messages.error(request, "Cannot remove the last admin from the team.")
            return redirect('teams:admin_list', slug=team.slug)
        
        self.team_slug = team.slug
        return super().dispatch(request, *args, **kwargs)
    
    def get_success_url(self):
        messages.success(self.request, "Admin removed successfully.")
        return reverse_lazy('teams:admin_list', kwargs={'slug': self.team_slug})


class AuthorizationView(LoginRequiredMixin, View):
    """
    Handle encrypted authorization access codes.
    
    URL: /teams/<team_slug>/authorization/<access_code>
    
    - Requires login
    - Checks if user is team admin
    - Validates access_code is base64-encoded Fernet-encrypted token
    - Checks if token age is less than 1 hour
    - Decrypts and stores the auth token for the user
    """
    
    def get_fernet_key(self):
        """Get Fernet encryption key from settings."""
        key = settings.FERNET_KEY
        if not key:
            raise ValueError(
                "FERNET_KEY not configured in settings. "
                "Add FERNET_KEY to your .env file. "
                "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
        # Ensure it's bytes
        if isinstance(key, str):
            key = key.encode()
        return key
    
    def get(self, request, slug, access_code):
        # Get team
        team = get_object_or_404(Team, slug=slug)
        
        # Check if user is team admin
        if not team.admins.filter(user=request.user).exists():
            return render(request, 'teams/authorization_error.html', {
                'error_type': 'unauthorized',
                'message': 'You do not have permission to access this resource.'
            }, status=403)
        
        try:
            # Initialize Fernet cipher
            fernet = Fernet(self.get_fernet_key())
            
            # Decode base64 access code
            try:
                encrypted_data = base64.urlsafe_b64decode(access_code)
            except Exception:
                return render(request, 'teams/authorization_error.html', {
                    'error_type': 'invalid',
                    'message': 'Invalid access code format.'
                }, status=400)
            
            # Decrypt with Fernet (includes timestamp validation)
            try:
                # ttl=3600 means 1 hour expiry
                decrypted_data = fernet.decrypt(encrypted_data, ttl=3600)
            except InvalidToken:
                return render(request, 'teams/authorization_error.html', {
                    'error_type': 'expired',
                    'message': 'This authorization link has expired. Links are valid for 1 hour.'
                }, status=410)
            
            # Parse decrypted JSON data
            try:
                payload = json.loads(decrypted_data.decode('utf-8'))
                # The 'token' field is the actual API token to be used
                reference_token = payload.get('token')
                if not reference_token:
                    raise ValueError("Missing token in payload")
            except (json.JSONDecodeError, ValueError) as e:
                return render(request, 'teams/authorization_error.html', {
                    'error_type': 'invalid',
                    'message': 'Invalid access code data.'
                }, status=400)
            
            # Check if this exact token key already exists
            existing_token = MultiToken.objects.filter(key=reference_token).first()
            
            if existing_token:
                if existing_token.user == request.user:
                    # Token already belongs to this user - success
                    return render(request, 'teams/authorization_success.html', {
                        'team': team,
                        'token_created': False
                    })
                else:
                    # Token belongs to different user - error
                    return render(request, 'teams/authorization_error.html', {
                        'error_type': 'invalid',
                        'message': 'This authorization token is already in use by another user.'
                    }, status=409)
            
            # Create a new MultiToken with the reference_token as the key
            token_instance = MultiToken.objects.create(user=request.user, key=reference_token)
            
            # Success - token created and stored
            return render(request, 'teams/authorization_success.html', {
                'team': team,
                'token_created': True
            })
            
        except Exception as e:
            # Catch-all for unexpected errors
            return render(request, 'teams/authorization_error.html', {
                'error_type': 'error',
                'message': f'An error occurred: {str(e)}'
            }, status=500)


class TeamExportView(TeamSlugMixin, TeamContextMixin, DetailView):
    """Export team standings (yearly) to CSV or PDF (public view).
    
    Query parameters:
    - format: 'csv' or 'pdf' (required)
    - year: year number (optional, defaults to current year)
    """
    model = Team
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    
    def get(self, request, *args, **kwargs):
        from datetime import date
        from scores.services.calculator import get_team_standings_by_year
        
        self.object = self.get_object()
        
        export_format = request.GET.get('format', 'csv').lower()
        year = request.GET.get('year')
        
        # Get current year as default
        today = date.today()
        if year:
            year = int(year)
        else:
            year = today.year
        
        # Get standings for the entire year
        standings = get_team_standings_by_year(self.team, year)
        
        # Filter only members with games played
        standings = [m for m in standings if hasattr(m, 'yearly_games') and m.yearly_games > 0]
        
        if export_format == 'pdf':
            return export_standings_to_pdf(self.team, standings, year=year, is_yearly=True)
        else:
            return export_standings_to_csv(self.team, standings, year=year, is_yearly=True)
