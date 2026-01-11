"""
Mixins for team-related views to reduce code duplication.
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from teams.models import Team


class TeamSlugMixin:
    """
    Automatically get team from URL slug parameter.
    Sets self.team for use in the view.
    Supports both 'slug' and 'team_slug' URL parameters.
    """
    team = None
    
    def dispatch(self, request, *args, **kwargs):
        slug_param = self.kwargs.get('team_slug') or self.kwargs.get('slug')
        self.team = get_object_or_404(Team, slug=slug_param)
        return super().dispatch(request, *args, **kwargs)
    
    def get_team(self):
        """Get the team for this view."""
        return self.team


class TeamAdminRequiredMixin(LoginRequiredMixin, TeamSlugMixin):
    """
    Ensure user is authenticated and is an admin of the team being accessed.
    Automatically gets team from URL slug and checks admin permission.
    """
    
    def dispatch(self, request, *args, **kwargs):
        # Get team from slug first (TeamSlugMixin)
        response = super().dispatch(request, *args, **kwargs)
        
        # Check if user is admin of this team
        if not self.team.is_admin(request.user):
            raise PermissionDenied("You do not have permission to manage this team.")
        
        return response


class TeamContextMixin:
    """
    Add team-related context to template context.
    Requires self.team to be set (use with TeamSlugMixin).
    """
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if hasattr(self, 'team') and self.team:
            context['team'] = self.team
            context['is_team_admin'] = self.team.is_admin(self.request.user) if self.request.user.is_authenticated else False
        return context
