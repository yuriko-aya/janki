from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, FormView
from django.views import View
import json

from taikai.forms import (
    TournamentForm,
    TournamentMemberForm,
    GenerateSessionsForm,
    TournamentSessionScoreForm,
)
from taikai.mixins import (
    TournamentAdminRequiredMixin,
    TournamentContextMixin,
    TournamentSlugMixin,
)
from taikai.models import Tournament, TournamentMember, TournamentSession, TournamentAdmin
from taikai.services.calculator import get_tournament_standings, get_tournament_member_game_history
from taikai.services.session_generator import (
    generate_fixed_sessions,
    generate_next_rank_hanchan,
    can_generate_next_rank_hanchan,
)


class TournamentListView(ListView):
    model = Tournament
    template_name = 'taikai/tournament_list.html'
    context_object_name = 'tournaments'
    paginate_by = 20

    def get_queryset(self):
        qs = Tournament.objects.filter(hidden=False)
        if self.request.user.is_authenticated:
            admin_ids = TournamentAdmin.objects.filter(
                user=self.request.user
            ).values_list('tournament_id', flat=True)
            qs = qs | Tournament.objects.filter(id__in=admin_ids, hidden=True)
        if self.request.user.is_authenticated and self.request.user.is_staff:
            return Tournament.objects.all().order_by('-created_at')
        return qs.distinct().order_by('-created_at')


class TournamentDetailView(TournamentSlugMixin, TournamentContextMixin, DetailView):
    model = Tournament
    template_name = 'taikai/tournament_detail.html'
    context_object_name = 'tournament'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_object(self, queryset=None):
        return get_object_or_404(
            Tournament.objects.prefetch_related('admins__user'),
            slug=self.kwargs[self.slug_url_kwarg],
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['standings'] = get_tournament_standings(self.tournament)
        context['substitutes'] = self.tournament.members.filter(is_substitute=True)
        return context


class TournamentCreateView(LoginRequiredMixin, CreateView):
    model = Tournament
    form_class = TournamentForm
    template_name = 'taikai/tournament_form.html'
    success_url = reverse_lazy('taikai:tournament_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        TournamentAdmin.objects.create(user=self.request.user, tournament=self.object)
        return response


class TournamentUpdateView(TournamentAdminRequiredMixin, UpdateView):
    model = Tournament
    form_class = TournamentForm
    template_name = 'taikai/tournament_form.html'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_success_url(self):
        return reverse_lazy('taikai:tournament_detail', kwargs={'slug': self.object.slug})


class TournamentMemberListView(TournamentAdminRequiredMixin, DetailView):
    model = Tournament
    template_name = 'taikai/member_list.html'
    context_object_name = 'tournament'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'


class TournamentMemberDetailView(TournamentSlugMixin, TournamentContextMixin, DetailView):
    """Display detailed stats for a tournament member (public view)."""
    model = TournamentMember
    template_name = 'taikai/member_detail.html'
    context_object_name = 'member'

    def get_object(self, queryset=None):
        return get_object_or_404(
            TournamentMember.objects.select_related('player', 'total_score'),
            pk=self.kwargs['pk'],
            tournament=self.tournament,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        member = self.object
        game_history = get_tournament_member_game_history(member)
        context['game_history'] = game_history

        if game_history:
            context['best_game'] = max(game_history, key=lambda g: g['calculated'])
            context['worst_game'] = min(game_history, key=lambda g: g['calculated'])

        paginator = Paginator(list(reversed(game_history)), 20)
        context['page_obj'] = paginator.get_page(self.request.GET.get('page', 1))

        standings = get_tournament_standings(self.tournament)
        context['rank'] = None
        for i, m in enumerate(standings, start=1):
            if m.pk == member.pk:
                context['rank'] = i
                break
        context['total_ranked'] = len(standings)

        ts = getattr(member, 'total_score', None)
        if ts and ts.games_played > 0:
            games = ts.games_played
            context['placement_bars'] = [
                {'label': '1st', 'count': ts.first_place_count, 'pct': ts.first_place_count / games * 100, 'color': '#27ae60'},
                {'label': '2nd', 'count': ts.second_place_count, 'pct': ts.second_place_count / games * 100, 'color': '#3498db'},
                {'label': '3rd', 'count': ts.third_place_count, 'pct': ts.third_place_count / games * 100, 'color': '#f39c12'},
                {'label': '4th', 'count': ts.fourth_place_count, 'pct': ts.fourth_place_count / games * 100, 'color': '#e74c3c'},
            ]
        else:
            context['placement_bars'] = []

        per_game_scores = [round(g['calculated'], 2) for g in game_history]
        cumulative_scores = []
        running = 0.0
        for score in per_game_scores:
            running += score
            cumulative_scores.append(round(running, 2))
        context['chart_labels_json'] = json.dumps([g['session_name'] for g in game_history])
        context['chart_scores_json'] = json.dumps(cumulative_scores)
        context['chart_per_game_json'] = json.dumps(per_game_scores)
        context['chart_placements_json'] = json.dumps([g['placement'] for g in game_history])
        context['player'] = member.player
        return context


class TournamentMemberCreateView(TournamentAdminRequiredMixin, TournamentContextMixin, CreateView):
    model = TournamentMember
    form_class = TournamentMemberForm
    template_name = 'taikai/member_form.html'

    def form_valid(self, form):
        form.instance.tournament = self.tournament
        messages.success(self.request, f"Member '{form.instance.name}' added.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('taikai:member_list', kwargs={'slug': self.tournament.slug})


class TournamentMemberUpdateView(LoginRequiredMixin, UpdateView):
    model = TournamentMember
    form_class = TournamentMemberForm
    template_name = 'taikai/member_form.html'

    def dispatch(self, request, *args, **kwargs):
        member = self.get_object()
        self.tournament_slug = member.tournament.slug
        if not member.tournament.is_admin(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tournament'] = self.get_object().tournament
        return context

    def get_success_url(self):
        return reverse_lazy('taikai:member_list', kwargs={'slug': self.tournament_slug})


class TournamentMemberDeleteView(LoginRequiredMixin, DeleteView):
    model = TournamentMember
    template_name = 'taikai/member_confirm_delete.html'

    def dispatch(self, request, *args, **kwargs):
        member = self.get_object()
        self.tournament_slug = member.tournament.slug
        if not member.tournament.is_admin(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy('taikai:member_list', kwargs={'slug': self.tournament_slug})


class GenerateSessionsView(TournamentAdminRequiredMixin, TournamentContextMixin, FormView):
    template_name = 'taikai/generate_sessions.html'
    form_class = GenerateSessionsForm

    def _redirect_if_not_fixed_mode(self):
        if not self.tournament.uses_fixed_hanchans():
            messages.error(
                self.request,
                'This tournament mode does not use bulk fixed session generation.',
            )
            return redirect('taikai:session_list', slug=self.tournament.slug)
        return None

    def get(self, request, *args, **kwargs):
        redirect_response = self._redirect_if_not_fixed_mode()
        if redirect_response:
            return redirect_response
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        redirect_response = self._redirect_if_not_fixed_mode()
        if redirect_response:
            return redirect_response
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            count = generate_fixed_sessions(self.tournament)
        except ValueError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        messages.success(self.request, f'Generated {count} fixed session(s).')
        return redirect('taikai:session_list', slug=self.tournament.slug)


class GenerateRankHanchanView(TournamentAdminRequiredMixin, View):
    """Generate the next rank-based hanchan one at a time."""

    def post(self, request, *args, **kwargs):
        allowed, message = can_generate_next_rank_hanchan(self.tournament)
        if not allowed:
            messages.error(request, message)
            return redirect('taikai:session_list', slug=self.tournament.slug)
        try:
            count = generate_next_rank_hanchan(self.tournament)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect('taikai:session_list', slug=self.tournament.slug)
        messages.success(request, f'Generated {count} session(s). {message}')
        return redirect('taikai:session_list', slug=self.tournament.slug)


class TournamentSessionListView(TournamentSlugMixin, TournamentContextMixin, DetailView):
    model = Tournament
    template_name = 'taikai/session_list.html'
    context_object_name = 'tournament'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        member_id = self.request.GET.get('member')
        sessions = self.tournament.sessions.prefetch_related('scores__member').all()
        if member_id:
            sessions = sessions.filter(scores__member_id=member_id).distinct()
        context['sessions'] = sessions
        context['members'] = self.tournament.members.order_by('name')
        context['selected_member_id'] = member_id or ''
        can_rank, rank_message = can_generate_next_rank_hanchan(self.tournament)
        context['can_generate_rank'] = can_rank
        context['rank_generate_message'] = rank_message
        return context


class TournamentSessionEditView(TournamentAdminRequiredMixin, TournamentContextMixin, FormView):
    template_name = 'taikai/session_edit.html'
    form_class = TournamentSessionScoreForm

    def dispatch(self, request, *args, **kwargs):
        self.session = get_object_or_404(
            TournamentSession,
            pk=kwargs['pk'],
            tournament__slug=kwargs['slug'],
        )
        self.tournament = self.session.tournament
        if not self.tournament.is_admin(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['session'] = self.session
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['session'] = self.session
        context['tournament'] = self.tournament
        return context

    def form_valid(self, form):
        from taikai.services.calculator import update_session_scores
        try:
            update_session_scores(self.session, form.get_score_data())
        except ValueError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        messages.success(self.request, f'Scores updated for {self.session.name}.')
        return redirect('taikai:session_list', slug=self.tournament.slug)
