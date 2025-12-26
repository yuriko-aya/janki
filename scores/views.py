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
    get_team_standings_by_month
)
from teams.models import Team


class RawScoreListView(LoginRequiredMixin, ListView):
    """List all raw scores for a team (admin view)."""
    model = RawScore
    template_name = 'scores/rawscore_list.html'
    context_object_name = 'scores'
    paginate_by = 50
    
    def dispatch(self, request, *args, **kwargs):
        team = get_object_or_404(Team, slug=self.kwargs['team_slug'])
        if not team.admins.filter(user=request.user).exists():
            raise PermissionDenied("You do not have permission to view this team's scores.")
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        team = get_object_or_404(Team, slug=self.kwargs['team_slug'])
        return RawScore.objects.filter(member__team=team).select_related('member').order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['team'] = get_object_or_404(Team, slug=self.kwargs['team_slug'])
        return context


class SessionSubmitView(LoginRequiredMixin, FormView):
    """Submit all 4 scores for a session at once."""
    form_class = SessionScoresForm
    template_name = 'scores/session_submit.html'
    
    def dispatch(self, request, *args, **kwargs):
        team = get_object_or_404(Team, slug=self.kwargs['team_slug'])
        if not team.admins.filter(user=request.user).exists():
            raise PermissionDenied("You do not have permission to submit scores for this team.")
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        team = get_object_or_404(Team, slug=self.kwargs['team_slug'])
        kwargs['team'] = team
        return kwargs
    
    def form_valid(self, form):
        team = get_object_or_404(Team, slug=self.kwargs['team_slug'])
        session_id = form.cleaned_data['session_id']
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
            submit_session_scores(session_id, team, score_data, session_date=session_date)
            messages.success(self.request, f"Session {session_id} scores submitted successfully!")
            return redirect('teams:member_list', slug=team.slug)
        except Exception as e:
            messages.error(self.request, f"Error submitting scores: {str(e)}")
            return self.form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['team'] = get_object_or_404(Team, slug=self.kwargs['team_slug'])
        return context


class SessionEditView(LoginRequiredMixin, FormView):
    """Edit all 4 scores for an existing session."""
    form_class = SessionEditForm
    template_name = 'scores/session_edit.html'
    
    def dispatch(self, request, *args, **kwargs):
        team = get_object_or_404(Team, slug=self.kwargs['team_slug'])
        if not team.admins.filter(user=request.user).exists():
            raise PermissionDenied("You do not have permission to edit scores for this team.")
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        team = get_object_or_404(Team, slug=self.kwargs['team_slug'])
        session_id = self.kwargs['session_id']
        kwargs['team'] = team
        kwargs['session_id'] = session_id
        
        # Pre-populate form with existing scores if not POST
        if self.request.method != 'POST':
            raw_scores = RawScore.objects.filter(
                member__team=team,
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
        team = get_object_or_404(Team, slug=self.kwargs['team_slug'])
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
            update_session_scores(session_id, team, score_data, session_date=session_date)
            messages.success(self.request, f"Session {session_id} updated successfully!")
            return redirect('teams:member_list', slug=team.slug)
        except Exception as e:
            messages.error(self.request, f"Error updating scores: {str(e)}")
            return self.form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['team'] = get_object_or_404(Team, slug=self.kwargs['team_slug'])
        context['session_id'] = self.kwargs['session_id']
        context['is_edit'] = True
        return context


class StandingsView(DetailView):
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
        team = self.get_object()
        
        # Get month and year from request parameters, default to current
        today = date.today()
        month = int(self.request.GET.get('month', today.month))
        year = int(self.request.GET.get('year', today.year))
        
        # Validate month
        if month < 1 or month > 12:
            month = today.month
        
        # Get standings filtered by month/year
        standings = get_team_standings_by_month(team, month, year)
        for rank, member in enumerate(standings, start=1):
            member.rank = rank
        
        context['standings'] = standings
        context['selected_month'] = month
        context['selected_year'] = year
        context['months'] = list(range(1, 13))
        context['current_year'] = today.year
        
        return context


class SessionsView(DetailView):
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
        
        context = super().get_context_data(**kwargs)
        team = self.get_object()
        
        # Get month and year from request parameters, default to current
        today = date.today()
        month = int(self.request.GET.get('month', today.month))
        year = int(self.request.GET.get('year', today.year))
        page_number = self.request.GET.get('page', 1)
        
        # Validate month
        if month < 1 or month > 12:
            month = today.month
        
        # Get all sessions for this team in the selected month/year
        from collections import defaultdict
        
        raw_scores = RawScore.objects.filter(
            member__team=team,
            created_at__year=year,
            created_at__month=month
        ).select_related('member').order_by('created_at', 'session_id')
        
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
                'scores': []
            }
            
            for idx, raw_score in enumerate(sorted_scores):
                placement = idx + 1
                
                # Calculate Uma based on placement (using team's uma settings)
                uma_map = {
                    1: team.uma_first,
                    2: team.uma_second,
                    3: team.uma_third,
                    4: team.uma_fourth
                }
                uma = uma_map.get(placement, 0)
                
                # Calculate base score
                base_score = (raw_score.score - team.target_point) / 1000.0
                
                # Calculate final score
                calculated = base_score + uma
                if raw_score.chombo > 0 and team.chombo_enabled:
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
        
        # Sort sessions by date (most recent first)
        sessions.sort(key=lambda x: x['session_date'], reverse=True)
        
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
        
        # Check if user is admin
        if self.request.user.is_authenticated:
            context['is_team_admin'] = team.admins.filter(user=self.request.user).exists()
        else:
            context['is_team_admin'] = False
        
        return context
