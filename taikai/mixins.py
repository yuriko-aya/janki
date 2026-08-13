"""Mixins for tournament views."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from taikai.models import Tournament


class TournamentSlugMixin:
    tournament = None

    def dispatch(self, request, *args, **kwargs):
        slug_param = self.kwargs.get('tournament_slug') or self.kwargs.get('slug')
        self.tournament = get_object_or_404(Tournament, slug=slug_param)
        return super().dispatch(request, *args, **kwargs)


class TournamentAdminRequiredMixin(TournamentSlugMixin, LoginRequiredMixin):
    def handle_no_permission(self):
        raise PermissionDenied('You must be logged in to access this page.')

    def dispatch(self, request, *args, **kwargs):
        slug_param = self.kwargs.get('tournament_slug') or self.kwargs.get('slug')
        self.tournament = get_object_or_404(Tournament, slug=slug_param)

        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if not self.tournament.is_admin(request.user):
            raise PermissionDenied('You do not have permission to manage this tournament.')

        return super(TournamentSlugMixin, self).dispatch(request, *args, **kwargs)


class TournamentContextMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if hasattr(self, 'tournament') and self.tournament:
            context['tournament'] = self.tournament
            user = self.request.user
            context['is_tournament_admin'] = (
                user.is_authenticated and self.tournament.is_admin(user)
            )
        return context
