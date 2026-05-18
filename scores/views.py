from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, FormView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy
from django.contrib import messages
from datetime import datetime, date

from scores.models import RawScore, CalculatedScore
from scores.forms import RawScoreForm, SessionScoresForm, SessionEditForm
from scores.services.calculator import (
    validate_session_complete,
    submit_session_scores,
    update_session_scores,
    get_team_standings,
    get_team_standings_by_month,
    recalculate_team_scores
)
from scores.export_utils import export_standings_to_csv, export_standings_to_pdf
from teams.models import Team
from teams.mixins import TeamAdminRequiredMixin, TeamSlugMixin, TeamContextMixin


class RawScoreListView(TeamAdminRequiredMixin, TeamContextMixin, ListView):
    """List all raw scores for a team (admin view)."""
    model = RawScore
    template_name = 'scores/rawscore_list.html'
    context_object_name = 'scores'
    paginate_by = 50
    
    def get_queryset(self):
        # Show all scores (archived and non-archived) in admin view
        return RawScore.objects.filter(member__team=self.team).select_related('member').order_by('-session_date', '-created_at')


class SessionSubmitView(TeamAdminRequiredMixin, TeamContextMixin, FormView):
    """Submit all 4 scores for a session at once."""
    form_class = SessionScoresForm
    template_name = 'scores/session_submit.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['team'] = self.team
        return kwargs
    
    def form_valid(self, form):
        now = datetime.now()
        session_id = now.strftime("%Y-%m-%d %H:%M")
        session_date = now.date()

        # Prepare score data
        score_data = []
        for i in range(4):
            member = form.cleaned_data.get(f'member_{i}')
            score = form.cleaned_data.get(f'score_{i}')
            chombo = form.cleaned_data.get(f'chombo_{i}', 0)
            if member and score is not None:
                score_data.append({
                    'member_id': member.id,
                    'score': score,
                    'chombo': chombo
                })
        
        try:
            submit_session_scores(session_id, self.team, score_data, session_date=session_date)
            messages.success(self.request, f"Session {session_id} scores submitted successfully!")
            return redirect('teams:member_list', slug=self.team.slug)
        except Exception as e:
            messages.error(self.request, f"Error submitting scores: {str(e)}")
            return self.form_invalid(form)


class SessionEditView(TeamAdminRequiredMixin, TeamContextMixin, FormView):
    """Edit all 4 scores for an existing session."""
    form_class = SessionEditForm
    template_name = 'scores/session_edit.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        session_id = self.kwargs['session_id']
        kwargs['team'] = self.team
        kwargs['session_id'] = session_id
        
        # Pre-populate form with existing scores if not POST
        if self.request.method != 'POST':
            raw_scores = RawScore.objects.filter(
                member__team=self.team,
                session_id=session_id
            ).select_related('member').order_by('placement')
            
            if raw_scores.exists():
                initial_data = {
                    'session_id': session_id,
                    'session_date': raw_scores.first().session_date
                }
                for i, raw_score in enumerate(raw_scores):
                    initial_data[f'member_{i}'] = raw_score.member
                    initial_data[f'score_{i}'] = raw_score.score
                    initial_data[f'chombo_{i}'] = raw_score.chombo
                kwargs['initial'] = initial_data
        
        return kwargs
    
    def form_valid(self, form):
        session_id = self.kwargs['session_id']
        session_date = form.cleaned_data.get('session_date')
        
        # Prepare score data
        score_data = []
        for i in range(4):
            member = form.cleaned_data.get(f'member_{i}')
            score = form.cleaned_data.get(f'score_{i}')
            chombo = form.cleaned_data.get(f'chombo_{i}', 0)
            if member and score is not None:
                score_data.append({
                    'member_id': member.id,
                    'score': score,
                    'chombo': chombo
                })
        
        try:
            update_session_scores(session_id, self.team, score_data, session_date=session_date)
            messages.success(self.request, f"Session {session_id} updated successfully!")
            return redirect('teams:member_list', slug=self.team.slug)
        except Exception as e:
            messages.error(self.request, f"Error updating scores: {str(e)}")
            return self.form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['session_id'] = self.kwargs['session_id']
        context['is_edit'] = True
        return context


class StandingsView(TeamSlugMixin, TeamContextMixin, DetailView):
    """Display team standings (public view - shows calculated scores only).
    
    Supports filtering by month/year. Default is current month.
    Query parameters: month (1-12) and year (YYYY)
    """
    model = Team
    template_name = 'scores/standings.html'
    context_object_name = 'team'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get month and year from request parameters, default to current
        today = date.today()
        month = int(self.request.GET.get('month', today.month))
        year = int(self.request.GET.get('year', today.year))
        
        # Validate month
        if month < 1 or month > 12:
            month = today.month
        
        # Get standings filtered by month/year
        standings = get_team_standings_by_month(self.team, month, year)
        for rank, member in enumerate(standings, start=1):
            member.rank = rank
        
        context['standings'] = standings
        context['selected_month'] = month
        context['selected_year'] = year
        context['months'] = list(range(1, 13))
        context['current_year'] = today.year
        
        return context


class SessionsView(TeamSlugMixin, TeamContextMixin, DetailView):
    """Display session details (public view - shows all sessions for a month).
    
    Supports filtering by month/year. Default is current month.
    Paginated at 10 sessions per page.
    Query parameters: month (1-12), year (YYYY), page (default: 1)
    """
    model = Team
    template_name = 'scores/sessions.html'
    context_object_name = 'team'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    
    def get_context_data(self, **kwargs):
        from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
        from collections import defaultdict
        
        context = super().get_context_data(**kwargs)
        
        # Get month and year from request parameters, default to current
        today = date.today()
        month = int(self.request.GET.get('month', today.month))
        year = int(self.request.GET.get('year', today.year))
        page_number = self.request.GET.get('page', 1)
        
        # Validate month
        if month < 1 or month > 12:
            month = today.month
        
        # Get all sessions for this team in the selected month/year (include archived)
        raw_scores = RawScore.objects.filter(
            member__team=self.team,
            session_date__year=year,
            session_date__month=month
        ).select_related('member').order_by('session_date', 'created_at', 'session_id')
        
        # Group by session_id
        sessions_dict = defaultdict(list)
        for raw_score in raw_scores:
            sessions_dict[raw_score.session_id].append(raw_score)
        
        # Build session data
        sessions = []
        for session_id, scores in sessions_dict.items():
            # Only include complete sessions (4 players)
            if len(scores) != 4:
                continue
            
            # Sort scores by raw score (descending) to determine placement
            sorted_scores = sorted(scores, key=lambda x: x.score, reverse=True)
            
            # Calculate details for each score
            session_data = {
                'session_id': session_id,
                'session_date': scores[0].session_date or scores[0].created_at,
                'archived': scores[0].archived,  # Add archived status
                'scores': []
            }
            
            # Uma map using team's settings
            uma_map = {
                1: self.team.uma_first,
                2: self.team.uma_second,
                3: self.team.uma_third,
                4: self.team.uma_fourth
            }
            
            for idx, raw_score in enumerate(sorted_scores):
                # Calculate placement, handling ties
                score_value = raw_score.score
                tied_scores = [s for s in sorted_scores if s.score == score_value]
                
                if len(tied_scores) > 1:
                    # Calculate shared placement for tied players
                    first_tied_idx = next(i for i, s in enumerate(sorted_scores) if s.score == score_value)
                    placement = sum(range(first_tied_idx + 1, first_tied_idx + len(tied_scores) + 1)) / len(tied_scores)
                    
                    # Calculate shared Uma by averaging the tied positions' Uma values
                    tied_positions = range(first_tied_idx + 1, first_tied_idx + len(tied_scores) + 1)
                    uma = sum(uma_map.get(pos, 0) for pos in tied_positions) / len(tied_scores)
                else:
                    # No tie - normal placement
                    placement = idx + 1
                    uma = uma_map.get(placement, 0)
                
                # Calculate base score
                base_score = (raw_score.score - self.team.target_point) / 1000.0
                
                # Calculate final score
                calculated = base_score + uma
                if raw_score.chombo > 0 and self.team.chombo_enabled:
                    calculated -= (30 * raw_score.chombo)
                
                session_data['scores'].append({
                    'member_name': raw_score.member.name,
                    'raw_score': raw_score.score,
                    'placement': placement,
                    'base_score': base_score,
                    'uma': uma,
                    'chombo': raw_score.chombo,
                    'calculated_score': calculated
                })
            
            sessions.append(session_data)
        
        # Sort sessions by date (most recent first), then by session_id (descending)
        sessions.sort(key=lambda x: (x['session_date'], x['session_id']), reverse=True)
        
        # Paginate sessions (10 per page)
        paginator = Paginator(sessions, 10)
        try:
            sessions_page = paginator.page(page_number)
        except PageNotAnInteger:
            sessions_page = paginator.page(1)
        except EmptyPage:
            sessions_page = paginator.page(paginator.num_pages)
        
        context['sessions'] = sessions_page
        context['total_sessions'] = len(sessions)
        context['selected_month'] = month
        context['selected_year'] = year
        context['months'] = list(range(1, 13))
        context['current_year'] = today.year
        
        return context


class ArchiveManagementView(TeamAdminRequiredMixin, TeamContextMixin, FormView):
    """Manage archived scores by year (admin view)."""
    template_name = 'scores/archive_management.html'
    
    def get_form_class(self):
        from scores.forms import ArchiveYearForm
        return ArchiveYearForm
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        from scores.services.calculator import get_archived_years, get_available_years
        context['archived_years'] = get_archived_years(self.team)
        context['available_years'] = get_available_years(self.team)
        
        return context
    
    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        
        from scores.forms import ArchiveYearForm
        form = ArchiveYearForm(request.POST)
        
        if form.is_valid():
            year = form.cleaned_data['year']
            
            from scores.services.calculator import archive_scores_by_year, unarchive_scores_by_year
            
            if action == 'archive':
                count = archive_scores_by_year(self.team, year)
                # Force recalculate all team members
                recalculate_team_scores(self.team)
                messages.success(request, f"Archived {count} scores from year {year}")
            elif action == 'unarchive':
                count = unarchive_scores_by_year(self.team, year)
                # Force recalculate all team members
                recalculate_team_scores(self.team)
                messages.success(request, f"Unarchived {count} scores from year {year}")
            else:
                messages.error(request, "Invalid action")
        else:
            messages.error(request, "Invalid year")
        
        return redirect('scores:archive_management', team_slug=self.team.slug)


class StandingsExportView(TeamSlugMixin, TeamContextMixin, DetailView):
    """Export team standings to CSV or PDF (public view).
    
    Query parameters:
    - format: 'csv' or 'pdf' (required)
    - month: month number (1-12) (optional)
    - year: year number (optional)
    """
    model = Team
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        export_format = request.GET.get('format', 'csv').lower()
        month = request.GET.get('month')
        year = request.GET.get('year')
        
        # Get current date for defaults
        today = date.today()
        
        # Parse month and year
        if month:
            month = int(month)
            if month < 1 or month > 12:
                month = today.month
        else:
            month = today.month
        
        if year:
            year = int(year)
        else:
            year = today.year
        
        # Get standings for the specified month/year
        standings = get_team_standings_by_month(self.team, month, year)
        
        # Filter only members with games played
        standings = [m for m in standings if hasattr(m, 'monthly_games') and m.monthly_games > 0]
        
        if export_format == 'pdf':
            return export_standings_to_pdf(self.team, standings, month=month, year=year)
        else:
            return export_standings_to_csv(self.team, standings, month=month, year=year)
