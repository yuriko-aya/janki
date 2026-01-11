# Quick Migration Guide for Developers

This guide helps developers understand the new patterns introduced in the refactoring.

---

## For View Development

### OLD Pattern: Team Admin Permission Check
```python
# ❌ OLD - Don't do this anymore
class MyView(LoginRequiredMixin, DetailView):
    def dispatch(self, request, *args, **kwargs):
        team = get_object_or_404(Team, slug=self.kwargs['team_slug'])
        if not team.admins.filter(user=request.user).exists():
            raise PermissionDenied("...")
        return super().dispatch(request, *args, **kwargs)
```

### NEW Pattern: Use TeamAdminRequiredMixin
```python
# ✅ NEW - Use this instead
from teams.mixins import TeamAdminRequiredMixin, TeamContextMixin

class MyView(TeamAdminRequiredMixin, TeamContextMixin, DetailView):
    # self.team is automatically available
    # Permission check is automatic
    # Context includes 'team' and 'is_team_admin'
    pass
```

### Available Mixins
```python
from teams.mixins import TeamSlugMixin, TeamAdminRequiredMixin, TeamContextMixin

# TeamSlugMixin
# - Automatically gets team from URL slug
# - Sets self.team
# - Supports both 'slug' and 'team_slug' URL parameters

# TeamAdminRequiredMixin (includes TeamSlugMixin)
# - Requires authentication
# - Gets team from slug
# - Checks admin permission
# - Raises PermissionDenied if not admin

# TeamContextMixin
# - Adds 'team' to context
# - Adds 'is_team_admin' to context
```

---

## For API Development

### OLD Pattern: API Responses
```python
# ❌ OLD - Don't do this anymore
return Response({
    'success': True,
    'message': 'Action completed',
    'data': {...}
}, status=status.HTTP_200_OK)

return Response({
    'error': 'Something went wrong'
}, status=status.HTTP_400_BAD_REQUEST)
```

### NEW Pattern: Use API Utils
```python
# ✅ NEW - Use this instead
from scores.api_utils import (
    success_response,
    error_response,
    permission_denied_response,
    not_found_response,
    validation_error_response
)

# Success response
return success_response(
    'Action completed',
    {'data': {...}},
    status.HTTP_200_OK  # optional, defaults to 200
)

# Error response
return error_response('Something went wrong')

# Permission denied
return permission_denied_response('Custom message')  # optional message

# Not found
return not_found_response('Resource not found')

# Validation errors
return validation_error_response(serializer.errors)
```

### Team Admin Check in API
```python
# ❌ OLD
if not team.admins.filter(user=request.user).exists():
    return Response({'error': '...'}, status=status.HTTP_403_FORBIDDEN)

# ✅ NEW
if not team.is_admin(request.user):
    return permission_denied_response('Custom message')
```

---

## For Scoring Logic

### OLD Pattern: Manual Placement Calculation
```python
# ❌ OLD - Don't repeat this logic
tied_players = [s for s in sorted_scores if s.score == member_score_value]
if len(tied_players) > 1:
    first_tied_idx = next(i for i, s in enumerate(sorted_scores) if s.score == member_score_value)
    placement = sum(range(first_tied_idx + 1, first_tied_idx + len(tied_players) + 1)) / len(tied_players)
else:
    placement = ...
```

### NEW Pattern: Use Helper Functions
```python
# ✅ NEW - Use helper functions
from scores.services.calculator import (
    calculate_placement_with_ties,
    calculate_uma_for_placement,
    calculate_session_score,
    get_uma_map
)

# Calculate placement
sorted_scores = sorted(scores, key=lambda x: x.score, reverse=True)
placement = calculate_placement_with_ties(score_value, sorted_scores)

# Get Uma bonus
uma = calculate_uma_for_placement(placement, team)

# Calculate final score (includes chombo)
final_score = calculate_session_score(
    raw_score_value,
    placement,
    uma,
    team,
    chombo_count
)

# Get Uma map
uma_map = get_uma_map(team)  # {1: 15, 2: 5, 3: -5, 4: -15}
```

### Recalculating Scores
```python
# ❌ OLD - Don't loop manually
for member in team.members.all():
    from scores.services.calculator import recalculate_member_score
    recalculate_member_score(member)

# ✅ NEW - Use bulk functions
from scores.services.calculator import recalculate_team_scores, recalculate_members

# Recalculate entire team
recalculate_team_scores(team)

# Recalculate specific members
recalculate_members(affected_members)
```

---

## For Email Sending

### OLD Pattern: Duplicate Email Logic
```python
# ❌ OLD - Don't duplicate this
class MyView(FormView):
    def send_verification_email(self, user, token):
        verification_url = self.request.build_absolute_uri(...)
        subject = 'Verify Your Email...'
        # ... lots of code
```

### NEW Pattern: Use Email Service
```python
# ✅ NEW - Use centralized service
from accounts.services import send_verification_email

# In your view
send_verification_email(self.request, user, token)
```

---

## Common Patterns

### Accessing Team in Views
```python
# With TeamSlugMixin or TeamAdminRequiredMixin
class MyView(TeamAdminRequiredMixin, ...):
    def get_queryset(self):
        # self.team is automatically available
        return RawScore.objects.filter(member__team=self.team)
    
    def form_valid(self, form):
        # Use self.team instead of get_object_or_404
        submit_session_scores(session_id, self.team, score_data)
```

### Adding Context in Templates
```python
# With TeamContextMixin
class MyView(TeamSlugMixin, TeamContextMixin, DetailView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # context['team'] already set
        # context['is_team_admin'] already set
        # Add your custom context here
        return context
```

---

## Testing Your Changes

```bash
# Always run after making changes
python manage.py check

# Test specific functionality
python manage.py test teams.tests
python manage.py test scores.tests
python manage.py test accounts.tests

# Run all tests
python manage.py test
```

---

## Common Mistakes to Avoid

### ❌ Don't mix old and new patterns
```python
# BAD - mixing patterns
class MyView(TeamAdminRequiredMixin, ...):
    def dispatch(self, request, *args, **kwargs):
        team = get_object_or_404(Team, slug=self.kwargs['team_slug'])  # ❌ Redundant!
        return super().dispatch(request, *args, **kwargs)
```

### ❌ Don't manually check permissions when using mixins
```python
# BAD - permission already checked by mixin
class MyView(TeamAdminRequiredMixin, ...):
    def get_queryset(self):
        if not self.team.is_admin(self.request.user):  # ❌ Already checked!
            raise PermissionDenied()
```

### ❌ Don't forget to call super() in get_context_data
```python
# BAD - loses context from mixins
class MyView(TeamContextMixin, ...):
    def get_context_data(self, **kwargs):
        context = {}  # ❌ Lost team and is_team_admin!
        return context

# GOOD
class MyView(TeamContextMixin, ...):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)  # ✅ Preserves mixin context
        return context
```

---

## Questions?

If you encounter issues or have questions about the new patterns:
1. Check [REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md) for details
2. Check [CODE_REDUNDANCY_ANALYSIS.md](CODE_REDUNDANCY_ANALYSIS.md) for rationale
3. Look at existing refactored views for examples

---

**Last Updated:** January 4, 2026
