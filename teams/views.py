from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy
from teams.models import Team, Member
from teams.forms import TeamForm, MemberForm
from scores.services.calculator import get_team_standings


class TeamListView(ListView):
    """List all teams (public view - no auth required)."""
    model = Team
    template_name = 'teams/team_list.html'
    context_object_name = 'teams'
    paginate_by = 20


class TeamDetailView(DetailView):
    """Display team details and standings (public view - no auth required)."""
    model = Team
    template_name = 'teams/team_detail.html'
    context_object_name = 'team'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        team = self.get_object()
        # Get standings sorted by calculated score
        context['standings'] = get_team_standings(team)
        return context


class TeamCreateView(LoginRequiredMixin, CreateView):
    """Create a new team (admin-only - creates TeamAdmin link)."""
    model = Team
    form_class = TeamForm
    template_name = 'teams/team_form.html'
    success_url = reverse_lazy('teams:team_list')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        # Create TeamAdmin link
        from accounts.models import TeamAdmin
        TeamAdmin.objects.create(user=self.request.user, team=self.object)
        return response


class TeamUpdateView(LoginRequiredMixin, UpdateView):
    """Update a team (admin-only - checks user is team admin)."""
    model = Team
    form_class = TeamForm
    template_name = 'teams/team_form.html'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    
    def dispatch(self, request, *args, **kwargs):
        team = self.get_object()
        if team.admin.user != request.user:
            raise PermissionDenied("You do not have permission to edit this team.")
        return super().dispatch(request, *args, **kwargs)
    
    def get_success_url(self):
        return reverse_lazy('teams:team_detail', kwargs={'slug': self.object.slug})


class MemberListView(DetailView):
    """Display all members of a team (admin view)."""
    model = Team
    template_name = 'teams/member_list.html'
    context_object_name = 'team'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    
    def dispatch(self, request, *args, **kwargs):
        team = self.get_object()
        if team.admin.user != request.user:
            raise PermissionDenied("You do not have permission to manage this team.")
        return super().dispatch(request, *args, **kwargs)


class MemberCreateView(LoginRequiredMixin, CreateView):
    """Add a new member to a team (admin-only)."""
    model = Member
    form_class = MemberForm
    template_name = 'teams/member_form.html'
    
    def dispatch(self, request, *args, **kwargs):
        team = get_object_or_404(Team, slug=self.kwargs['slug'])
        if team.admin.user != request.user:
            raise PermissionDenied("You do not have permission to manage this team.")
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        team = get_object_or_404(Team, slug=self.kwargs['slug'])
        member = form.save(commit=False)
        member.team = team
        member.save()
        return redirect('teams:member_list', slug=team.slug)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['team'] = get_object_or_404(Team, slug=self.kwargs['slug'])
        return context


class MemberUpdateView(LoginRequiredMixin, UpdateView):
    """Update a team member (admin-only)."""
    model = Member
    form_class = MemberForm
    template_name = 'teams/member_form.html'
    
    def dispatch(self, request, *args, **kwargs):
        member = self.get_object()
        self.team_slug = member.team.slug
        if member.team.admin.user != request.user:
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
        if member.team.admin.user != request.user:
            raise PermissionDenied("You do not have permission to manage this member.")
        return super().dispatch(request, *args, **kwargs)
    
    def get_success_url(self):
        return reverse_lazy('teams:member_list', kwargs={'slug': self.team_slug})
