# GitHub Copilot Instructions

## Overview
This repository contains a Django web application for **Mahjong score tracking across multiple teams**.  
Each team is managed by a team admin and includes members who submit scores for individual Mahjong sessions.

**Core Domain Model:**
- Teams (managed by team admins) → Members (belong to a team) → RawScores (per session) → CalculatedScores (aggregated)
- Sessions must have exactly 4 score entries (one per player)
- CalculatedScore is the sum of all RawScores for a member across all sessions
- Public pages show team standings but hide admin-only operations

Copilot should generate Django code consistent with the structure and rules below.

---

## Tech Stack
- **Framework:** Django (latest LTS or stable)
- **Database:** PostgreSQL
- **ORM:** Django ORM only; no raw SQL unless essential
- **API Framework:** Django REST Framework (DRF) only if file already uses DRF
- **Environment Config:** django-environ for database credentials and settings

---

## Architecture & Project Structure

### Django Apps & Responsibilities
```
accounts/          User authentication, TeamAdmin model (extends User)
teams/             Team, Member models; team CRUD operations
scores/            RawScore, CalculatedScore models; scoring logic & aggregation
templates/         HTML templates organized by app (accounts/, teams/, scores/)
static/            CSS, JS, images (minimize inline styles)
```

### Data Flow
1. **Score Submission:** Member submits RawScore via form → validated against session (exactly 4 entries)
2. **Aggregation:** Signal or scheduled task recalculates CalculatedScore for affected member
3. **Public Display:** Team page shows CalculatedScores; admin-only views show RawScores & session details

### Key Design Patterns
- **Service Module:** `scores/services/calculator.py` handles score aggregation logic (keeps views thin)
- **Model Methods:** Business logic lives on models (e.g., `Team.get_standings()`, `Member.total_score()`)
- **Signals:** Use Django signals sparingly; prefer explicit service calls in views for clarity
- **Team Isolation:** All queries must filter by `team` to enforce multi-tenant isolation

### Folder Structure (Suggested)
```
project_root/
├── accounts/
│   ├── models.py          # User, TeamAdmin
│   ├── views.py
│   ├── forms.py
│   ├── urls.py
│   └── templates/accounts/
├── teams/
│   ├── models.py          # Team, Member
│   ├── views.py
│   ├── forms.py
│   ├── urls.py
│   └── templates/teams/
├── scores/
│   ├── models.py          # RawScore, CalculatedScore
│   ├── views.py
│   ├── forms.py
│   ├── urls.py
│   ├── services/
│   │   └── calculator.py  # Score aggregation logic
│   └── templates/scores/
├── templates/             # Shared/base templates
├── static/                # CSS, JS, images
├── manage.py
├── requirements.txt
├── .env                   # Local development (never commit)
└── README.md
```

### Models

#### User & Auth
```python
# accounts/models.py
class TeamAdmin(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='team_admin')
    team = models.OneToOneField('teams.Team', on_delete=models.CASCADE, related_name='admin')
    created_at = models.DateTimeField(auto_now_add=True)

class EmailVerificationToken(models.Model):
    """Token for email verification during registration. Tokens expire after ACCOUNT_ACTIVATION_TIMEOUT_DAYS."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='verification_token')
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

#### Team
```python
class Team(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, db_index=True)
    
    # Scoring configuration (team-customizable)
    start_point = models.IntegerField(default=30000)  # Starting chips for each player
    target_point = models.IntegerField(default=30000)  # Target score for calculating base points
    
    # Uma (placement bonus) configuration
    uma_first = models.IntegerField(default=15)  # Uma bonus for 1st place
    uma_second = models.IntegerField(default=5)  # Uma bonus for 2nd place
    uma_third = models.IntegerField(default=-5)  # Uma bonus for 3rd place
    uma_fourth = models.IntegerField(default=-15)  # Uma bonus for 4th place
    
    # Chombo (bankruptcy) configuration
    chombo_enabled = models.BooleanField(default=True)  # Enable chombo penalty (-30 points)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

#### Member
```python
class Member(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='members', db_index=True)
    name = models.CharField(max_length=100)
    join_date = models.DateField(auto_now_add=True)
```

#### RawScore (per session entry)
```python
class RawScore(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='raw_scores', db_index=True)
    score = models.IntegerField()  # Mahjong score value (e.g., 25000, 18000)
    placement = models.IntegerField(null=True, blank=True)  # Player position in session (1-4)
    chombo = models.IntegerField(default=0)  # Number of chombos (bankruptcies) - can be stacked
    session_id = models.CharField(max_length=100, db_index=True)  # Group 4 scores per session
    session_date = models.DateField(null=True, blank=True)  # Date of the game session (for historical records)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Constraint: Exactly 4 RawScores per session per team
```

#### CalculatedScore (aggregated)
```python
class CalculatedScore(models.Model):
    member = models.OneToOneField(Member, on_delete=models.CASCADE, related_name='calculated_score')
    total = models.FloatField(default=0.0)  # Sum of all calculated scores
    games_played = models.IntegerField(default=0)  # Number of complete sessions played
    average_per_game = models.FloatField(default=0.0)  # Average score per game
    average_placement = models.FloatField(default=0.0)  # Average placement (1st-4th)
    chombo_count = models.IntegerField(default=0)  # Total number of chombos
    updated_at = models.DateTimeField(auto_now=True)
```

---

## Coding Style & Conventions
- **Views:** Use Django class-based views (ListView, DetailView, CreateView, UpdateView). Inherit PermissionRequiredMixin for admin-only views.
- **URL routing:** Use path() instead of url() (Django 2.0+).
- **Logic placement:** Keep views thin—move business logic to model methods or service modules.
- **Naming:** Use snake_case for functions/variables, PascalCase for classes.
- **Migrations:** Always create and commit migrations for schema changes.
- **Environment:** Use django-environ for secrets/database configuration; never hardcode credentials.
- **Filtering:** Always filter querysets by `team` at the view layer to enforce multi-tenant isolation.

---

## Views and Permissions
- **Admin-only views:** Require login and check user is the team admin for the team being modified.
- **A team admin may manage only:**
  - Their own team details
  - Team members
  - Scores within their team
- **Public views (no auth required):**
  - Team overview/roster (name, member list)
  - Team standings (CalculatedScores, rankings)
- **Never expose on public pages:**
  - Individual RawScore entries (show only aggregated CalculatedScore)
  - Admin credentials or settings
  - Members from other teams

---

## Score Calculation Rules (Mahjong)

### Overview
This application implements **Mahjong scoring** with placement-based bonuses (Uma) and bankruptcy penalties (Chombo).

### Scoring Formula
For each session, a member's score is calculated as:

```
Calculated Score = ((Raw Score - target_point) / 1,000) + Uma Bonus + (Chombo Penalty × chombo_count)
```

**Components:**

1. **Base Score:** `(Raw Score - target_point) / 1,000`
   - Normalizes raw scores to a scale around 0
   - `target_point` is **team-configurable** (default: 30,000)
   - Scores are divided by 1,000 for readability

2. **Uma Bonus (Placement Bonus):**
   - Determined by final placement in the session
   - Based on raw score ranking (highest = 1st place)
   - **Team-configurable** values (defaults shown):
     * **1st place:** +15 points (`team.uma_first`)
     * **2nd place:** +5 points (`team.uma_second`)
     * **3rd place:** -5 points (`team.uma_third`)
     * **4th place:** -15 points (`team.uma_fourth`)
   - Uma bonuses should sum to zero across the 4 players (recommended)
   - **Tie Handling:** When multiple players have the same raw score:
     * **Shared Placement:** Tied players receive the average of the positions they occupy
       - Example: Two players tied for 1st occupy positions 1 and 2 → both get placement 1.5
       - Example: Three players tied for 2nd occupy positions 2, 3, and 4 → all get placement 3.0
     * **Shared Uma:** Tied players split the total Uma for the positions they occupy equally
       - Example: Tied for 1st-2nd → Uma = (15 + 5) / 2 = +10 each
       - Example: Tied for 3rd-4th → Uma = (-5 + -15) / 2 = -10 each
     * This ensures fairness and maintains zero-sum scoring

3. **Chombo Penalty (Bankruptcy):**
   - Applied if player went bankrupt (`RawScore.chombo > 0`)
   - **Chombo is an integer** (can be stacked: 0, 1, 2, etc.)
   - Penalty: **-30 points per chombo** (applied after Uma calculation)
   - Can be **disabled per team** via `team.chombo_enabled`
   - Total penalty: -30 × `RawScore.chombo`
   - Only affects that player's score

### Session Requirements
- A Mahjong session consists of **exactly 4 players**
- A session is only counted if it has exactly 4 score entries
- Incomplete sessions are skipped during aggregation
- One session = one game of Mahjong

### Example Calculation
**Session 1 raw scores:** Alice=30,000, Bob=35,000, Charlie=25,000, Diana=10,000

| Player  | Raw Score | Placement | Base | Uma | Chombo | Total |
|---------|-----------|-----------|------|-----|--------|-------|
| Bob     | 35,000    | 1st       | +5   | +15 | -      | +20   |
| Alice   | 30,000    | 2nd       | +0   | +5  | -      | +5    |
| Charlie | 25,000    | 3rd       | -5   | -5  | -      | -10   |
| Diana   | 10,000    | 4th       | -20  | -15 | -      | -35   |
| **SUM** |           |           |      |     |        | **-20** |

**Session 2 with Chombo:** Alice=28,000 (no chombo), Bob=30,000, Charlie=32,000 **CHOMBO**, Diana=15,000

| Player  | Raw Score | Placement | Base | Uma | Chombo | Total |
|---------|-----------|-----------|------|-----|--------|-------|
| Charlie | 32,000    | 1st       | +2   | +15 | -30    | -13   |
| Bob     | 30,000    | 2nd       | +0   | +5  | -      | +5    |
| Alice   | 28,000    | 3rd       | -2   | -5  | -      | -7    |
| Diana   | 15,000    | 4th       | -15  | -15 | -      | -30   |

**Aggregate (after 2 sessions):** Alice: +5-7=-2, Bob: +20+5=+25, Charlie: -10-13=-23, Diana: -35-30=-65

**Session 3 with Ties:** Alice=30,000, Bob=30,000 (tied for 1st), Charlie=20,000, Diana=20,000 (tied for 3rd)

| Player  | Raw Score | Placement | Base | Uma        | Chombo | Total |
|---------|-----------|-----------|------|------------|--------|-------|
| Alice   | 30,000    | 1.5       | +0   | +10 (shared) | -    | +10   |
| Bob     | 30,000    | 1.5       | +0   | +10 (shared) | -    | +10   |
| Charlie | 20,000    | 3.5       | -10  | -10 (shared) | -    | -20   |
| Diana   | 20,000    | 3.5       | -10  | -10 (shared) | -    | -20   |
| **SUM** |           |           |      |            |        | **-20** |

*Note: Tied players share placements (1.5, 3.5) and split Uma bonuses equally (+10, -10) to maintain fairness and zero-sum scoring.*

### Implementation Details

**RawScore Model:**
```python
class RawScore(models.Model):
    member = models.ForeignKey('teams.Member', on_delete=models.CASCADE, related_name='raw_scores', db_index=True)
    score = models.IntegerField()  # Raw Mahjong score (e.g., 25000, 32000)
    placement = models.FloatField(null=True, blank=True)  # Player position in session (1-4, can be fractional for ties like 1.5)
    chombo = models.IntegerField(default=0)  # Number of chombos (bankruptcies) - can be stacked
    session_id = models.CharField(max_length=100, db_index=True)
    session_date = models.DateField(null=True, blank=True)  # Date of the game session
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['member', 'session_id']  # One score per player per session
```

**CalculatedScore Model:**
```python
class CalculatedScore(models.Model):
    member = models.OneToOneField('teams.Member', on_delete=models.CASCADE, related_name='calculated_score')
    total = models.FloatField(default=0.0)  # Aggregate score
    games_played = models.IntegerField(default=0)  # Only complete sessions (4 players)
    average_per_game = models.FloatField(default=0.0)  # total / games_played
    average_placement = models.FloatField(default=0.0)  # Average placement (1st-4th)
    chombo_count = models.IntegerField(default=0)  # Total number of chombos
```

**Service Layer (scores/services/calculator.py):**
- `recalculate_member_score(member)`: Triggers `compute_stats()` and saves
- `compute_stats()` on CalculatedScore model method: Implements full Mahjong scoring logic
  - Groups RawScores by session_id
  - Validates exactly 4 scores per session
  - Determines placement for member by sorting raw scores descending
  - Uses team-configurable parameters: `target_point`, `uma_first/second/third/fourth`, `chombo_enabled`
  - Calculates: `((score - target_point) / 1000) + uma + (chombo_penalty × chombo_count)`
  - Sums across all complete sessions
  - Computes: total, games_played, average_per_game, average_placement, chombo_count
- `validate_session_complete(session_id, team)`: Ensures session has exactly 4 scores
- `submit_session_scores(session_id, team, score_data, session_date=None)`: Create new session with 4 scores atomically
- `update_session_scores(session_id, team, score_data, session_date=None)`: Update existing session scores
- `get_session_details(session_id, team)`: Returns placement/uma/chombo breakdown for all 4 players in a session
- `get_team_standings(team)`: Get all members sorted by calculated score
- `get_team_standings_by_month(team, month, year)`: Get standings filtered by specific month/year

**Service Functions Example:**
```python
# scores/services/calculator.py
def validate_session_complete(session_id, team):
    """Ensure exactly 4 scores exist for this session+team."""
    count = RawScore.objects.filter(member__team=team, session_id=session_id).count()
    if count != 4:
        raise ValidationError(f"Session {session_id} must have exactly 4 scores, found {count}")

def submit_session_scores(session_id, team, score_data, session_date=None):
    """Submit all scores for a session at once.
    Args:
        session_id: The session identifier
        team: The Team object
        score_data: List of dicts with {'member_id': int, 'score': int, 'chombo': int}
        session_date: Optional date of the session
    Returns:
        List of created RawScore objects
    """
    # Implementation validates exactly 4 scores, creates RawScores, recalculates affected members
```

### Key Rules for Implementation
1. **Placement is determined by raw score ranking** (highest raw score = 1st place, lowest = 4th place)
2. **Tie handling is automatic:** When multiple players have the same raw score:
   - They share placements (e.g., tied for 1st-2nd = placement 1.5 each)
   - They split Uma bonuses equally (e.g., tied for 1st-2nd = (+15+5)/2 = +10 each)
   - Placement is stored as FloatField to support fractional values
3. **Uma is always applied** based on placement, even if a player has negative base score
4. **Chombo penalty is applied after Uma** (so a 1st place with chombo: +2 + 15 - 30 = -13)
5. **Incomplete sessions are ignored** (a member with 1 game shows games_played=1, another member in 2 complete sessions shows games_played=2)
6. **CalculatedScore.total is a FloatField** to support decimal calculations
7. **RawScore.chombo is an IntegerField (default=0)**; can be 0, 1, 2, etc. for multiple chombos
8. **Placement can be pre-calculated and stored** in `RawScore.placement` or calculated on-the-fly from score ranking
9. **Team parameters are configurable**: target_point, uma values, chombo_enabled
10. **Session date tracking**: `RawScore.session_date` allows historical record keeping

---

## Security Requirements
- **Team isolation:** All querysets must filter by `team` to prevent cross-team data leakage.
- **Admin verification:** Check `request.user == team.admin.user` before allowing modifications.

- **Public views:** Never expose admin-only data (RawScores, admin settings, member details beyond name).
- **Template safety:** Escape user-generated content; use Django's auto-escaping.
- **Session handling:** Validate that score submissions belong to the correct team.

**Example Permission Check:**
```python
# teams/views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

class TeamUpdateView(LoginRequiredMixin, UpdateView):
    queryset = Team.objects.all()
    
    def dispatch(self, request, *args, **kwargs):
        team = self.get_object()
        if team.admin.user != request.user:
            raise PermissionDenied("You do not have permission to edit this team.")
        return super().dispatch(request, *args, **kwargs)
```

---

## Database Conventions
- Use PostgreSQL UUIDField where appropriate.
- Use auto_now_add for timestamps.
- Add indexes for:
  - team slug
  - member foreign key
  - session ID

---

## REST API
The application includes a REST API for score submission using Django REST Framework.

### API Structure
```
scores/
├── api_views.py         # API endpoints (SessionSubmitAPIView, SessionUpdateAPIView, etc.)
├── api_serializers.py   # DRF serializers (SessionScoresSerializer, ScoreEntrySerializer)
└── api_urls.py          # API URL routing
```

### Authentication
- **Token-based authentication** using DRF's `TokenAuthentication`
- Tokens generated via Django admin for team admins
- All API endpoints require authentication
- Team admin can only submit/update scores for their own team

### Key Endpoints
```
POST /api/teams/{team_slug}/sessions/          # Submit new session (4 scores)
PUT  /api/teams/{team_slug}/sessions/{id}/     # Update existing session
GET  /api/teams/{team_slug}/standings/         # Get team standings
GET  /api/teams/{team_slug}/sessions/          # List sessions
```

### Request/Response Format
```json
// POST /api/teams/{team_slug}/sessions/
{
  "session_id": "2025-12-24-001",
  "session_date": "2025-12-24",  // optional
  "scores": [
    {"member_name": "Alice", "score": 35000, "chombo": 0},
    {"member_name": "Bob", "score": 28000, "chombo": 1},
    {"member_name": "Charlie", "score": 25000, "chombo": 0},
    {"member_name": "Diana", "score": 12000, "chombo": 0}
  ]
}

// Response
{
  "success": true,
  "message": "Session 2025-12-24-001 scores submitted successfully",
  "session_id": "2025-12-24-001",
  "scores_created": 4
}
```

### API Serializers
- **ScoreEntrySerializer**: Validates individual score entries (member_name, score, chombo)
- **SessionScoresSerializer**: Validates entire session (exactly 4 scores, no duplicates)
- Serializers validate that member exists in team and all required fields are present

### API Best Practices
- Use explicit field declarations in serializers
- Validate team ownership before any mutations
- Return meaningful error messages with appropriate HTTP status codes
- Use `select_related()` and `prefetch_related()` for query optimization
- Enforce exactly 4 scores per session in serializer validation

---

## Templates and UI
- Use Django templates.
- Bootstrap or Tailwind may be used only if already in the project.
- Avoid inline CSS/JS (use static/css/style.css and static/js/app.js).
- Organize templates by app:
  ```
  templates/
  ├── base.html                    # Base template with common structure
  ├── accounts/
  │   ├── login.html
  │   ├── register.html
  │   ├── email_verification.html
  │   ├── registration_pending.html
  │   └── turnstile_widget.html    # Cloudflare Turnstile CAPTCHA
  ├── teams/
  │   ├── team_list.html
  │   ├── team_detail.html
  │   ├── team_form.html
  │   ├── member_list.html
  │   ├── member_form.html
  │   └── member_confirm_delete.html
  ├── scores/
  │   ├── standings.html           # Team standings page
  │   ├── sessions.html            # List of sessions
  │   ├── session_submit.html      # Submit new session
  │   ├── session_edit.html        # Edit existing session
  │   └── rawscore_list.html       # Admin view of raw scores
  └── admin/
      └── login.html               # Custom admin login template
  ```

### Template Tags
Custom template filters are defined in `scores/templatetags/scores_filters.py`:

```python
# Load in templates with: {% load scores_filters %}

{{ month_num|month_name_filter }}    # Convert 1-12 to "January"-"December"
{{ month_num|short_month_name }}     # Convert 1-12 to "Jan"-"Dec"
{{ value|mul:3 }}                    # Multiply value by 3
```

### Template Best Practices
- Always extend from base.html
- Use {% block %} for customization points
- Escape user-generated content (Django auto-escapes by default)
- Use {% url %} tag for URL generation, never hardcode URLs
- Use {% static %} tag for static file URLs

---

## Examples

### Good
```python
class Team(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### Bad
```python
class Team(models.Model):
    title = models.TextField()
    created = models.DateTimeField()
```
