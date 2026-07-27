from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
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
from teams.models import Team, Member, Player
from teams.forms import TeamForm, MemberForm, AddTeamAdminForm
from teams.mixins import TeamAdminRequiredMixin, TeamSlugMixin, TeamContextMixin
from teams.services import apply_member_user_link
from accounts.models import TeamAdmin
from scores.services.calculator import get_team_standings, get_inactive_members, get_team_standings_by_month, get_team_standings_by_year, get_member_game_history, get_player_game_history
from datetime import date
from scores.export_utils import export_standings_to_csv, export_standings_to_pdf


class TeamListView(ListView):
    """List all teams (public view - no auth required)."""
    model = Team
    template_name = 'teams/team_list.html'
    context_object_name = 'teams'
    paginate_by = 20
    
    def get_queryset(self):
        # Staff users see all teams including hidden ones
        if self.request.user.is_authenticated and self.request.user.is_staff:
            return Team.objects.all().order_by('-created_at')

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
        today = date.today()
        context['standings'] = get_team_standings_by_year(self.team, today.year)
        context['monthly_standings'] = get_team_standings_by_month(self.team, today.month, today.year)
        context['inactive_members'] = get_inactive_members(self.team)
        context['current_month'] = today.strftime('%B %Y')
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

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['team'] = self.team
        return kwargs

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        if not form.is_valid():
            return self.form_invalid(form)

        member = form.save(commit=False)
        member.team = self.team
        member.player = Player.objects.create(name=member.name)
        member.save()
        try:
            apply_member_user_link(member, form.cleaned_data.get('linked_username', ''))
        except ValidationError as exc:
            player = member.player
            member.delete()
            if player.members.count() == 0:
                player.delete()
            form.add_error('linked_username', exc.messages[0] if exc.messages else str(exc))
            return self.form_invalid(form)
        messages.success(request, f"Member '{member.name}' added successfully.")
        return redirect('teams:member_list', slug=self.team.slug)


class MemberUpdateView(LoginRequiredMixin, UpdateView):
    """Update a team member (admin-only)."""
    model = Member
    form_class = MemberForm
    template_name = 'teams/member_form.html'
    
    def dispatch(self, request, *args, **kwargs):
        member = self.get_object()
        self.team_slug = member.team.slug
        self.member_team = member.team
        if not member.team.is_admin(request.user):
            raise PermissionDenied("You do not have permission to manage this member.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['team'] = self.member_team
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['team'] = self.get_object().team
        return context

    def form_valid(self, form):
        member = form.save()
        try:
            apply_member_user_link(member, form.cleaned_data.get('linked_username', ''))
        except ValidationError as exc:
            form.add_error('linked_username', exc.messages[0] if exc.messages else str(exc))
            return self.form_invalid(form)
        messages.success(self.request, f"Member '{member.name}' updated successfully.")
        return redirect(self.get_success_url())
    
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


class MemberDetailView(TeamSlugMixin, TeamContextMixin, DetailView):
    """Display detailed stats for a single member (public view - no auth required)."""
    model = Member
    template_name = 'teams/member_detail.html'
    context_object_name = 'member'

    def get_object(self):
        return get_object_or_404(Member, pk=self.kwargs['pk'], team=self.team)

    def get_context_data(self, **kwargs):
        from django.core.paginator import Paginator
        context = super().get_context_data(**kwargs)
        member = self.object

        stats = get_member_game_history(member)
        game_history = stats['game_history']  # chronological, used for chart data
        context['monthly_breakdown'] = stats['monthly_breakdown']

        if game_history:
            context['best_game'] = max(game_history, key=lambda g: g['calculated'])
            context['worst_game'] = min(game_history, key=lambda g: g['calculated'])

        # Paginate game history newest-first for the table (20 per page)
        paginator = Paginator(list(reversed(game_history)), 20)
        page_obj = paginator.get_page(self.request.GET.get('page', 1))
        context['game_history'] = game_history  # used for chart data and {% if %} check
        context['page_obj'] = page_obj

        # Rank in all-time standings
        standings = get_team_standings(self.team)
        context['rank'] = None
        for i, m in enumerate(standings, start=1):
            if m.pk == member.pk:
                context['rank'] = i
                break
        context['total_ranked'] = standings.count()

        # Placement distribution bars
        cs = getattr(member, 'calculated_score', None)
        if cs and cs.games_played > 0:
            games = cs.games_played
            context['placement_bars'] = [
                {'label': '1st', 'count': cs.first_place_count, 'pct': cs.first_place_count / games * 100, 'color': '#27ae60'},
                {'label': '2nd', 'count': cs.second_place_count, 'pct': cs.second_place_count / games * 100, 'color': '#3498db'},
                {'label': '3rd', 'count': cs.third_place_count, 'pct': cs.third_place_count / games * 100, 'color': '#f39c12'},
                {'label': '4th', 'count': cs.fourth_place_count, 'pct': cs.fourth_place_count / games * 100, 'color': '#e74c3c'},
            ]
        else:
            context['placement_bars'] = []

        # Chart data: cumulative score and per-game score over time
        per_game_scores = [round(g['calculated'], 2) for g in game_history]
        cumulative_scores = []
        running = 0.0
        for score in per_game_scores:
            running += score
            cumulative_scores.append(round(running, 2))
        chart_dates = [str(g['date']) for g in game_history]
        context['chart_dates_json'] = json.dumps(chart_dates)
        context['chart_scores_json'] = json.dumps(cumulative_scores)
        context['chart_per_game_json'] = json.dumps(per_game_scores)
        context['chart_placements_json'] = json.dumps([g['placement'] for g in game_history])

        context['player'] = member.player
        context['player_team_count'] = member.player.members.values('team').distinct().count()

        return context


class PlayerDetailView(DetailView):
    """Display combined stats for a player across all teams (public view)."""
    model = Player
    template_name = 'teams/player_detail.html'
    context_object_name = 'player'

    def get_context_data(self, **kwargs):
        from django.core.paginator import Paginator
        context = super().get_context_data(**kwargs)
        player = self.object

        stats = get_player_game_history(player)
        game_history = stats['game_history']
        summary = stats['summary']
        context['monthly_breakdown'] = stats['monthly_breakdown']
        context['team_summaries'] = stats['team_summaries']
        context['summary'] = summary

        if game_history:
            context['best_game'] = max(game_history, key=lambda g: g['calculated'])
            context['worst_game'] = min(game_history, key=lambda g: g['calculated'])

        paginator = Paginator(list(reversed(game_history)), 20)
        page_obj = paginator.get_page(self.request.GET.get('page', 1))
        context['game_history'] = game_history
        context['page_obj'] = page_obj

        games = summary['games_played']
        if games > 0:
            context['placement_bars'] = [
                {'label': '1st', 'count': summary['first_place_count'], 'pct': summary['first_place_count'] / games * 100, 'color': '#27ae60'},
                {'label': '2nd', 'count': summary['second_place_count'], 'pct': summary['second_place_count'] / games * 100, 'color': '#3498db'},
                {'label': '3rd', 'count': summary['third_place_count'], 'pct': summary['third_place_count'] / games * 100, 'color': '#f39c12'},
                {'label': '4th', 'count': summary['fourth_place_count'], 'pct': summary['fourth_place_count'] / games * 100, 'color': '#e74c3c'},
            ]
        else:
            context['placement_bars'] = []

        per_game_scores = [round(g['calculated'], 2) for g in game_history]
        cumulative_scores = []
        running = 0.0
        for score in per_game_scores:
            running += score
            cumulative_scores.append(round(running, 2))
        chart_dates = [str(g['date']) for g in game_history]
        context['chart_dates_json'] = json.dumps(chart_dates)
        context['chart_scores_json'] = json.dumps(cumulative_scores)
        context['chart_per_game_json'] = json.dumps(per_game_scores)
        context['chart_placements_json'] = json.dumps([g['placement'] for g in game_history])

        return context


class MemberMonthlyView(TeamSlugMixin, TeamContextMixin, DetailView):
    """Display monthly stats for a single member (public view - no auth required)."""
    model = Member
    template_name = 'teams/member_monthly.html'
    context_object_name = 'member'

    def get_object(self):
        return get_object_or_404(Member, pk=self.kwargs['pk'], team=self.team)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        member = self.object

        stats = get_member_game_history(member)
        game_history = stats['game_history']
        monthly_breakdown = stats['monthly_breakdown']

        # Determine available months for the selector
        available_months = [(row['year'], row['month']) for row in monthly_breakdown]

        # Parse requested month/year from query params, default to latest available
        today = date.today()
        try:
            req_year = int(self.request.GET.get('year', 0))
            req_month = int(self.request.GET.get('month', 0))
        except (ValueError, TypeError):
            req_year = req_month = 0

        if req_year and req_month and (req_year, req_month) in available_months:
            sel_year, sel_month = req_year, req_month
        elif available_months:
            sel_year, sel_month = available_months[-1]
        else:
            sel_year, sel_month = today.year, today.month

        context['sel_year'] = sel_year
        context['sel_month'] = sel_month
        context['available_months'] = available_months

        # Filter game history for selected month
        month_games = [
            g for g in game_history
            if g['date'].year == sel_year and g['date'].month == sel_month
        ]
        context['month_games'] = month_games

        # Monthly aggregate stats for selected month
        if month_games:
            total = sum(g['calculated'] for g in month_games)
            games_count = len(month_games)
            avg = total / games_count
            placements = [g['placement'] for g in month_games]
            avg_placement = sum(placements) / len(placements)
            chombo_total = sum(g['chombo'] for g in month_games)

            best_game = max(month_games, key=lambda g: g['calculated'])
            worst_game = min(month_games, key=lambda g: g['calculated'])

            from collections import Counter
            placement_counts = {1: 0, 2: 0, 3: 0, 4: 0}
            for p in placements:
                rounded = round(p)
                if rounded in placement_counts:
                    placement_counts[rounded] += 1

            context['month_total'] = total
            context['month_games_count'] = games_count
            context['month_avg'] = avg
            context['month_avg_placement'] = avg_placement
            context['month_chombo'] = chombo_total
            context['month_best_game'] = best_game
            context['month_worst_game'] = worst_game
            context['month_placement_bars'] = [
                {'label': '1st', 'count': placement_counts[1], 'pct': placement_counts[1] / games_count * 100, 'color': '#27ae60'},
                {'label': '2nd', 'count': placement_counts[2], 'pct': placement_counts[2] / games_count * 100, 'color': '#3498db'},
                {'label': '3rd', 'count': placement_counts[3], 'pct': placement_counts[3] / games_count * 100, 'color': '#f39c12'},
                {'label': '4th', 'count': placement_counts[4], 'pct': placement_counts[4] / games_count * 100, 'color': '#e74c3c'},
            ]

            # Chart data for selected month
            per_game_scores = [round(g['calculated'], 2) for g in month_games]
            running = 0.0
            cumulative_scores = []
            for s in per_game_scores:
                running += s
                cumulative_scores.append(round(running, 2))
            chart_dates = [str(g['date']) for g in month_games]
            context['chart_dates_json'] = json.dumps(chart_dates)
            context['chart_scores_json'] = json.dumps(cumulative_scores)
            context['chart_per_game_json'] = json.dumps(per_game_scores)
            context['chart_placements_json'] = json.dumps(placements)
        else:
            context['month_total'] = 0.0
            context['month_games_count'] = 0
            context['month_avg'] = 0.0
            context['month_avg_placement'] = None
            context['month_chombo'] = 0
            context['month_best_game'] = None
            context['month_worst_game'] = None
            context['month_placement_bars'] = []
            context['chart_dates_json'] = None
            context['chart_scores_json'] = None
            context['chart_per_game_json'] = None
            context['chart_placements_json'] = None

        # Prev / next month navigation
        if available_months:
            idx = available_months.index((sel_year, sel_month)) if (sel_year, sel_month) in available_months else -1
            context['prev_month'] = available_months[idx - 1] if idx > 0 else None
            context['next_month'] = available_months[idx + 1] if idx >= 0 and idx < len(available_months) - 1 else None
        else:
            context['prev_month'] = None
            context['next_month'] = None

        return context


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
