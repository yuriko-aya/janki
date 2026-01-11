# Code Redundancy Analysis

**Date:** January 4, 2026  
**Project:** Janki - Mahjong Score Tracking Application

This document identifies redundant features, functions, and code that can be merged or combined to improve maintainability and reduce duplication.

---

## 1. Duplicate Permission Checking Logic

### Issue: Team Admin Permission Checks
**Location:** Throughout `teams/views.py`, `scores/views.py`, and `scores/api_views.py`

**Current State:**
```python
# Pattern repeated 20+ times across views:
if not team.admins.filter(user=request.user).exists():
    raise PermissionDenied("You do not have permission...")
```

**Problem:** 
- Same permission check repeated in 20+ locations
- Inconsistent error messages
- Manual checks in every view's `dispatch()` method

**Recommendation:**
1. **Create a reusable mixin** for class-based views:
   ```python
   # teams/mixins.py (new file)
   class TeamAdminRequiredMixin(LoginRequiredMixin):
       """Ensure user is admin of the team being accessed."""
       def dispatch(self, request, *args, **kwargs):
           team = self.get_team()
           if not team.is_admin(request.user):
               raise PermissionDenied("You do not have permission to manage this team.")
           return super().dispatch(request, *args, **kwargs)
       
       def get_team(self):
           # Override in subclasses or auto-detect
           pass
   ```

2. **Use the existing `Team.is_admin()` method** consistently instead of `team.admins.filter(user=user).exists()`
   - Found instances where `is_admin()` is already defined but not used everywhere
   - Line 46 in `teams/models.py` defines `is_admin()` but it's only used in 1 place

3. **Create decorator for function-based views** (if any)

**Impact:** Reduces ~20 duplicate checks to 1 reusable mixin, improves consistency

---

## 2. Duplicate Email Sending Logic

### Issue: Duplicate `send_verification_email()` Method
**Location:** `accounts/views.py` lines 47 and 123

**Current State:**
```python
# RegisterView.send_verification_email() - lines 47-65
def send_verification_email(self, user, token):
    verification_url = self.request.build_absolute_uri(...)
    subject = 'Verify Your Email - Mahjong Score Tracker'
    # ... identical code ...

# RegistrationPendingView.send_verification_email() - lines 123-141
def send_verification_email(self, user, token):
    verification_url = self.request.build_absolute_uri(...)
    subject = 'Verify Your Email - Mahjong Score Tracker'
    # ... identical code ...
```

**Problem:**
- Exact same method duplicated in 2 classes
- Changes must be made in 2 places
- Violates DRY principle

**Recommendation:**
1. **Move to a utility function** or **service layer**:
   ```python
   # accounts/services.py (new file)
   def send_verification_email(request, user, token):
       """Send email verification link to user."""
       verification_url = request.build_absolute_uri(
           reverse_lazy('accounts:verify_email', kwargs={'token': token.token})
       )
       # ... rest of logic
   ```

2. **Or create a base mixin** for email verification:
   ```python
   # accounts/mixins.py
   class EmailVerificationMixin:
       def send_verification_email(self, user, token):
           # Single implementation
   ```

**Impact:** Removes 1 duplicate method, centralizes email logic

---

## 3. Duplicate Placement & Uma Calculation Logic

### Issue: Identical Scoring Logic Repeated 5+ Times
**Location:** 
- `scores/models.py` (CalculatedScore.compute_stats) lines 89-120
- `scores/services/calculator.py` (get_team_standings_by_month) lines 130-170
- `scores/services/calculator.py` (get_session_details) lines 370-410
- `scores/views.py` (SessionsView.get_context_data) lines 260-310

**Current State:**
Placement calculation and Uma logic duplicated:
```python
# Pattern 1: Calculate placement with tie handling
tied_players = [s for s in sorted_scores if s.score == member_score_value]
if len(tied_players) > 1:
    first_tied_idx = next(i for i, s in enumerate(sorted_scores) if s.score == member_score_value)
    placement = sum(range(first_tied_idx + 1, first_tied_idx + len(tied_players) + 1)) / len(tied_players)
else:
    placement = next(i + 1 for i, s in enumerate(sorted_scores) if s.member == self.member)

# Pattern 2: Uma map
uma_map = {
    1: team.uma_first,
    2: team.uma_second,
    3: team.uma_third,
    4: team.uma_fourth
}

# Pattern 3: Calculate shared Uma for ties
if len(tied_players) > 1:
    tied_positions = range(first_tied_idx + 1, first_tied_idx + len(tied_players) + 1)
    uma = sum(uma_map.get(pos, 0) for pos in tied_positions) / len(tied_players)
else:
    uma = uma_map.get(int(placement), 0)

# Pattern 4: Score calculation
calculated = (raw_score.score - team.target_point) / 1000.0 + uma
if raw_score.chombo > 0 and team.chombo_enabled:
    calculated -= (30 * raw_score.chombo)
```

**Problem:**
- Same complex logic repeated 5+ times
- High risk of bugs if only some instances are updated
- Difficult to maintain consistency

**Recommendation:**
Create helper functions in `scores/services/calculator.py`:

```python
def calculate_placement_with_ties(score, sorted_scores, member_identifier):
    """Calculate placement for a score, handling ties."""
    # Single implementation
    pass

def get_uma_for_placement(placement, team):
    """Get Uma bonus for a placement, handling fractional placements."""
    # Single implementation
    pass

def calculate_session_score(raw_score, placement, uma, team):
    """Calculate final score with chombo penalty."""
    # Single implementation
    pass

def get_uma_map(team):
    """Get Uma mapping from team configuration."""
    return {
        1: team.uma_first,
        2: team.uma_second,
        3: team.uma_third,
        4: team.uma_fourth
    }
```

**Impact:** Consolidates 5+ duplicate implementations into 3-4 reusable functions

---

## 4. Duplicate Turnstile Validation Logic

### Issue: Turnstile Mixin Used in Multiple Forms
**Location:** `accounts/forms.py`

**Current State:**
```python
class TurnstileMixin:
    """Mixin to validate Turnstile token in forms."""
    def clean(self):
        # Validation logic
    
    @staticmethod
    def verify_turnstile_token(token):
        # API call logic

# Used in:
- UserRegistrationForm (line 54)
- LoginForm (line 100)
- ResendVerificationEmailForm (line 113)
- AdminLoginForm (accounts/admin_views.py line 10)
```

**Problem:**
- While the mixin itself is good, the `turnstile_token` field is duplicated in each form

**Recommendation:**
Add the field to the mixin:
```python
class TurnstileMixin:
    """Mixin to validate Turnstile token in forms."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['turnstile_token'] = forms.CharField(
            widget=forms.HiddenInput(),
            required=False
        )
    
    # ... rest of validation
```

**Impact:** Minor improvement, removes 4 duplicate field definitions

---

## 5. Duplicate Queryset Filtering for Team Isolation

### Issue: Team Filtering Repeated in Multiple Views
**Location:** Throughout `scores/views.py`, `scores/api_views.py`, `teams/views.py`

**Current State:**
```python
# Pattern repeated in multiple views:
RawScore.objects.filter(member__team=team, ...)
Member.objects.filter(team=team, ...)
```

**Problem:**
- Boilerplate team filtering in every query
- Risk of forgetting team filter (security issue)

**Recommendation:**
Create custom managers/querysets:
```python
# scores/managers.py (new file)
class TeamScopedQuerySet(models.QuerySet):
    def for_team(self, team):
        return self.filter(member__team=team)

class RawScoreManager(models.Manager):
    def get_queryset(self):
        return TeamScopedQuerySet(self.model, using=self._db)
    
    def for_team(self, team):
        return self.get_queryset().for_team(team)

# In models.py
class RawScore(models.Model):
    objects = RawScoreManager()
    # ...

# Usage:
RawScore.objects.for_team(team).filter(session_id=session_id)
```

**Impact:** More readable code, enforces team isolation pattern

---

## 6. Duplicate "Get Team from Slug" Pattern

### Issue: Repeated `get_object_or_404(Team, slug=...)` 
**Location:** Throughout views

**Current State:**
```python
# Repeated 30+ times:
team = get_object_or_404(Team, slug=self.kwargs['team_slug'])
# or
team = get_object_or_404(Team, slug=self.kwargs['slug'])
```

**Recommendation:**
Add to TeamAdminRequiredMixin or create generic mixin:
```python
class TeamSlugMixin:
    """Automatically get team from URL slug."""
    team = None
    
    def dispatch(self, request, *args, **kwargs):
        slug_param = self.kwargs.get('team_slug') or self.kwargs.get('slug')
        self.team = get_object_or_404(Team, slug=slug_param)
        return super().dispatch(request, *args, **kwargs)
    
    def get_team(self):
        return self.team
```

**Impact:** Removes 30+ duplicate lines

---

## 7. Duplicate API Response Patterns

### Issue: Similar Response Structures in API Views
**Location:** `scores/api_views.py`, `teams/api_views.py`

**Current State:**
```python
# Success pattern repeated:
return Response({
    'success': True,
    'message': 'Session {session_id} ...',
    # ...
}, status=status.HTTP_201_CREATED)

# Error pattern repeated:
return Response({
    'error': 'You do not have permission...'
}, status=status.HTTP_403_FORBIDDEN)
```

**Recommendation:**
Create utility functions:
```python
# scores/api_utils.py (new file)
def success_response(message, data=None, status_code=status.HTTP_200_OK):
    response = {'success': True, 'message': message}
    if data:
        response.update(data)
    return Response(response, status=status_code)

def error_response(message, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({'error': message}, status=status_code)

def permission_denied_response(message="Permission denied"):
    return error_response(message, status.HTTP_403_FORBIDDEN)
```

**Impact:** More consistent API responses, less boilerplate

---

## 8. Duplicate Member Recalculation Calls

### Issue: Manual Recalculation Loops
**Location:** `scores/services/calculator.py` and `scores/views.py`

**Current State:**
```python
# Pattern repeated 4+ times:
for member in affected_members:
    recalculate_member_score(member)

# Or:
for member in team.members.all():
    from scores.services.calculator import recalculate_member_score
    recalculate_member_score(member)
```

**Recommendation:**
Create bulk recalculation function:
```python
def recalculate_team_scores(team):
    """Recalculate all members in a team."""
    for member in team.members.all():
        recalculate_member_score(member)

def recalculate_members(members):
    """Recalculate multiple members."""
    for member in members:
        recalculate_member_score(member)
```

**Impact:** Cleaner code, potential for optimization (bulk operations)

---

## 9. Duplicate Context Data in Templates

### Issue: Repeated Context Building
**Location:** Multiple DetailView subclasses

**Current State:**
```python
# Repeated in multiple views:
if self.request.user.is_authenticated:
    context['is_team_admin'] = team.admins.filter(user=self.request.user).exists()
else:
    context['is_team_admin'] = False
```

**Recommendation:**
Create context processor or base view:
```python
# teams/context_processors.py (new file)
def team_admin_context(request):
    """Add team admin status to context globally."""
    return {
        'is_team_admin_of': lambda team: team.is_admin(request.user) if request.user.is_authenticated else False
    }

# Or add to base view mixin
class TeamContextMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        team = self.get_team()
        context['is_team_admin'] = team.is_admin(self.request.user)
        return context
```

**Impact:** Less template context boilerplate

---

## 10. Duplicate Form Field Definitions

### Issue: Similar Form Fields Across Multiple Forms
**Location:** `teams/forms.py`, `scores/forms.py`

**Current State:**
```python
# SessionScoresForm and SessionEditForm have duplicate field definitions
# All forms repeat form-control CSS classes
```

**Recommendation:**
1. Use Django's `__init__()` to add common attributes
2. Consider using django-crispy-forms or django-widget-tweaks for consistent styling
3. Create base form classes for common patterns

**Impact:** Reduced CSS class duplication

---

## 11. Duplicate Admin Configuration

### Issue: Token Admin Registered Twice
**Location:** `scores/api_admin.py`

**Current State:**
```python
# Lines 35-55: CustomTokenAdmin
admin.site.register(Token, CustomTokenAdmin)

# Lines 58-74: TokenInline (for user admin)
# Lines 77-82: UserAdminWithToken
admin.site.unregister(User)
admin.site.register(User, UserAdminWithToken)
```

**Problem:**
- Token management available in 2 places (Token admin + User admin inline)
- Could be confusing for admins

**Recommendation:**
Choose one approach:
- Either Token standalone admin OR User inline, not both
- If keeping both, add comments explaining why

**Impact:** Cleaner admin interface

---

## 12. Unused/Redundant Model Methods

### Issue: `Member.total_score()` vs `CalculatedScore.total`
**Location:** `teams/models.py` line 92

**Current State:**
```python
class Member:
    def total_score(self):
        """Get the calculated score total for this member."""
        try:
            return self.calculated_score.total
        except:
            return 0
```

**Problem:**
- Simple wrapper that just returns `calculated_score.total`
- Bare `except` (bad practice)
- Only used in one place (or not at all)

**Recommendation:**
- Remove if unused
- If used, improve error handling:
  ```python
  def total_score(self):
      return getattr(self.calculated_score, 'total', 0)
  ```

**Impact:** Minor cleanup

---

## 13. Duplicate Session Validation

### Issue: Session Completeness Check Repeated
**Location:** Multiple places in `calculator.py` and `models.py`

**Current State:**
```python
# Pattern repeated 10+ times:
if len(session_scores) != 4:
    # Skip or raise error
```

**Recommendation:**
Use the existing `validate_session_complete()` function consistently:
```python
# Already exists at line 17 of calculator.py
def validate_session_complete(session_id, team):
    """Ensure exactly 4 scores exist for this session+team."""
    count = RawScore.objects.filter(member__team=team, session_id=session_id).count()
    if count != 4:
        raise ValidationError(...)
```

Use this instead of inline checks.

**Impact:** Consistency, single source of truth

---

## 14. Duplicate Import Statements

### Issue: Repeated Imports Within Functions
**Location:** Throughout `scores/views.py`, `calculator.py`

**Current State:**
```python
# Inside functions:
from scores.services.calculator import recalculate_member_score
from teams.models import Member
from datetime import datetime, date
```

**Recommendation:**
Move all imports to top of file (PEP 8 standard)

**Impact:** Better readability, faster import resolution

---

## Summary of Recommendations

| Priority | Issue | Location | Effort | Impact |
|----------|-------|----------|--------|--------|
| **HIGH** | Team admin permission checks | Views (20+ occurrences) | Medium | High |
| **HIGH** | Placement & Uma calculation logic | Models, Services, Views (5+ occurrences) | High | High |
| **MEDIUM** | Email sending logic | accounts/views.py | Low | Medium |
| **MEDIUM** | Team filtering pattern | All views | Medium | Medium |
| **MEDIUM** | Get team from slug pattern | All views | Low | Medium |
| **LOW** | Turnstile field duplication | Forms | Low | Low |
| **LOW** | API response patterns | API views | Low | Medium |
| **LOW** | Member recalculation loops | Services | Low | Low |
| **LOW** | Template context building | Views | Low | Low |
| **LOW** | Form field definitions | Forms | Low | Low |
| **LOW** | Admin token configuration | Admin | Low | Low |
| **LOW** | Member.total_score() method | Models | Very Low | Low |
| **LOW** | Session validation checks | Services | Low | Medium |
| **LOW** | Import statement placement | All files | Low | Low |

---

## Implementation Strategy

### Phase 1: High Priority (Week 1-2)
1. Create `teams/mixins.py` with `TeamAdminRequiredMixin`
2. Create placement/uma helper functions in `scores/services/calculator.py`
3. Refactor all views to use mixins
4. Refactor all scoring logic to use helpers

### Phase 2: Medium Priority (Week 3-4)
5. Create email service utility
6. Add custom model managers for team scoping
7. Create team slug mixin
8. Standardize API responses

### Phase 3: Low Priority (Week 5+)
9. Minor cleanups (imports, form fields, etc.)
10. Remove unused code
11. Add documentation for new utilities

---

## Testing Considerations

After implementing these changes:
1. **Unit tests** for new utility functions
2. **Integration tests** for refactored views
3. **Regression tests** to ensure scoring calculations remain correct
4. **Permission tests** to verify admin access control

---

## Notes

- All recommendations maintain backward compatibility with existing database schema
- No breaking changes to public API endpoints
- Templates require minimal changes
- Focus is on DRY (Don't Repeat Yourself) principle
- Secondary benefit: easier to add new features in the future

---

**End of Analysis**
