# Mahjong Score Tracker

A Django web application for tracking Mahjong scores across multiple teams with proper Japanese Mahjong scoring rules.

## Features

- **Multi-team support**: Multiple teams can be managed independently
- **Japanese Mahjong scoring**: Proper calculation with Uma (placement bonuses) and Chombo (bankruptcy penalties)
- **Customizable team settings**: Configure target points, Uma values, and Chombo rules per team
- **Score tracking**: Record individual scores for each player in Mahjong sessions
- **Monthly standings**: View team rankings with aggregated scores filtered by month/year
- **Session history**: Detailed view of all game sessions with placement and score breakdowns
- **REST API**: Submit and manage scores via API endpoints
- **Admin dashboard**: Team admins can manage members and submit scores
- **Public pages**: View-only access to team information and standings
- **Mobile responsive**: Fully optimized for mobile devices
- **Session archiving**: Archive old sessions to exclude from standings calculations

## Project Structure

```
project_root/
├── accounts/           # User authentication, TeamAdmin model, email verification
├── teams/              # Team and Member models, team CRUD operations
├── scores/             # RawScore, CalculatedScore, and scoring logic
│   ├── services/
│   │   └── calculator.py   # Score aggregation, Uma calculation, tie handling
│   ├── api_views.py        # REST API endpoints
│   ├── api_serializers.py  # DRF serializers
│   └── templatetags/       # Custom template filters
├── templates/          # HTML templates organized by app
│   ├── base.html
│   ├── accounts/
│   ├── teams/
│   └── scores/
├── static/             # CSS, JavaScript, images
│   ├── css/
│   │   └── style.css   # Main stylesheet with responsive design
│   └── js/
│       └── app.js
├── config/             # Django settings and URL configuration
├── manage.py
├── requirements.txt
├── .env.example        # Example environment variables
└── README.md
```

## Prerequisites

- Python 3.8+
- pip
- virtualenv (recommended)

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd janki
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv env
   source env/bin/activate  # On Windows: env\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create a `.env` file** (if needed for PostgreSQL)
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials
   ```

5. **Run migrations**
   ```bash
   python manage.py migrate
   ```

6. **Create a superuser** (admin account)
   ```bash
   python manage.py createsuperuser
   ```

7. **Collect static files**
   ```bash
   python manage.py collectstatic
   ```

8. **Start the development server**
   ```bash
   python manage.py runserver
   ```

9. **Access the application**
   - Main site: http://localhost:8000
   - Admin panel: http://localhost:8000/admin
   - Teams: http://localhost:8000/teams/

## Usage

### Creating a Team

1. Register an account at http://localhost:8000/accounts/register/
2. Verify your email (check console logs in development)
3. Login at http://localhost:8000/accounts/login/
4. Navigate to Teams → Create Team
5. Enter the team name and configure scoring settings
6. You are now the admin of this team

### Configuring Team Scoring Settings

Each team can customize their Mahjong scoring rules:

- **Start Point**: Initial chips for each player (default: 30,000)
- **Target Point**: Target score for calculating base points (default: 30,000)
- **Uma (Placement Bonus)**:
  - 1st place: +15 points (customizable)
  - 2nd place: +5 points (customizable)
  - 3rd place: -5 points (customizable)
  - 4th place: -15 points (customizable)
- **Chombo Penalty**: Enable/disable bankruptcy penalty (-30 points per chombo)

### Adding Members

1. Go to your team's detail page
2. Click "Manage Members"
3. Click "+ Add Member" and enter member names

### Managing Team Admins

1. Go to your team's detail page
2. Click "Manage Admins"
3. Add other users as team admins by entering their username
4. Multiple admins can manage the same team

### Submitting Scores

1. From the team page, click "Submit Session"
2. Enter a unique Session ID (e.g., "2026-01-04-game1")
3. Enter the session date (optional, defaults to today)
4. Select each of the 4 players and enter their raw scores
5. Check "Chombo" for any player who went bankrupt
6. Click "Submit Session"
7. Scores are automatically calculated using the team's Uma and Chombo settings

### Score Calculation

For each session, a member's score is calculated as:

```
Calculated Score = ((Raw Score - Target Point) / 1,000) + Uma Bonus + (Chombo Penalty × Chombo Count)
```

**Example:**
- Raw Score: 35,000
- Target Point: 30,000
- Placement: 1st (Uma: +15)
- Chombo: 0

**Calculation:**
```
Base = (35,000 - 30,000) / 1,000 = +5.0
Uma = +15
Total = 5.0 + 15 = +20.0 points
```

**Tie Handling:**
- Tied players share placements (e.g., tied for 1st-2nd = placement 1.5 each)
- Uma bonuses are split equally among tied players

### Viewing Standings

1. Navigate to any team's page
2. Click "View Standings" to see player rankings
3. Filter by month and year to view historical standings
4. Standings are public (no login required)
5. Players with 0 games played are automatically hidden

### Viewing Sessions

1. From the standings page, click "View Sessions"
2. See detailed breakdown of each session including:
   - Raw scores
   - Placement (1st-4th)
   - Base score calculation
   - Uma bonuses
   - Chombo penalties
   - Final calculated score
3. Team admins can edit sessions

### Archiving Sessions

1. Team admins can archive old sessions
2. Archived sessions are excluded from standings calculations
3. Historical data is preserved but not counted

## Models

### Team
- `name`: Team name
- `slug`: URL-friendly identifier (auto-generated)
- `start_point`: Starting chips for each player (default: 30,000)
- `target_point`: Target score for base point calculation (default: 30,000)
- `uma_first`: Uma bonus for 1st place (default: +15)
- `uma_second`: Uma bonus for 2nd place (default: +5)
- `uma_third`: Uma bonus for 3rd place (default: -5)
- `uma_fourth`: Uma bonus for 4th place (default: -15)
- `chombo_enabled`: Enable chombo penalty (default: True)
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp

### Member
- `team`: ForeignKey to Team
- `name`: Member name
- `join_date`: Date member joined
- `created_at`: Creation timestamp

### RawScore (per session entry)
- `member`: ForeignKey to Member
- `score`: Raw Mahjong score value (e.g., 25000, 35000)
- `placement`: Player position in session (1-4, can be fractional for ties)
- `chombo`: Number of chombos (bankruptcies) - can be stacked (0, 1, 2, etc.)
- `session_id`: Groups 4 scores per session (must be unique per session)
- `session_date`: Date of the game session
- `archived`: Whether this score is archived (excluded from standings)
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp

### CalculatedScore (aggregated per member)
- `member`: OneToOneField to Member
- `total`: Sum of all calculated scores
- `games_played`: Number of complete sessions (4 players)
- `average_per_game`: Average calculated score per game
- `average_placement`: Average placement (1st-4th)
- `first_place_count`: Number of 1st place finishes
- `second_place_count`: Number of 2nd place finishes
- `third_place_count`: Number of 3rd place finishes
- `fourth_place_count`: Number of 4th place finishes
- `chombo_count`: Total number of chombos
- `updated_at`: Last update timestamp

### TeamAdmin
- `user`: OneToOneField to Django User
- `team`: ManyToManyField to Team (a user can admin multiple teams)
- `created_at`: Creation timestamp

## Architecture

### Data Flow

1. **Score Submission**: Team admin submits 4 scores for a session
2. **Validation**: System validates exactly 4 scores per session per team
3. **Storage**: Scores stored as RawScore objects
4. **Aggregation**: CalculatedScore automatically updated for each member
5. **Display**: Public pages show aggregated CalculatedScores only

### Service Layer

Business logic is centralized in `scores/services/calculator.py`:
- `validate_session_complete()`: Ensures exactly 4 scores per session
- `recalculate_member_score()`: Updates CalculatedScore with proper Uma and Chombo calculations
- `get_team_standings()`: Returns ranked members sorted by total score
- `get_team_standings_by_month()`: Returns standings filtered by specific month/year
- `submit_session_scores()`: Atomic score submission for new sessions
- `update_session_scores()`: Update existing session scores
- `get_session_details()`: Get placement/uma/chombo breakdown for a session

### REST API

The application includes a REST API for score submission:

**Authentication:** Token-based (DRF TokenAuthentication)

**Endpoints:**
- `POST /api/teams/{slug}/sessions/` - Submit new session (4 scores)
- `PUT /api/teams/{slug}/sessions/{id}/` - Update existing session
- `GET /api/teams/{slug}/standings/` - Get team standings
- `GET /api/teams/{slug}/sessions/` - List sessions

**Example API Request:**
```bash
curl -X POST http://localhost:8000/api/teams/my-team/sessions/ \
  -H "Authorization: Token YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "2026-01-04-001",
    "session_date": "2026-01-04",
    "scores": [
      {"member_name": "Alice", "score": 35000, "chombo": 0},
      {"member_name": "Bob", "score": 28000, "chombo": 0},
      {"member_name": "Charlie", "score": 25000, "chombo": 0},
      {"member_name": "Diana", "score": 12000, "chombo": 0}
    ]
  }'
```

See `API_DOCUMENTATION.md` for full API details.

### Security

- **Team isolation**: All queries filtered by team to prevent cross-team data leakage
- **Permission checks**: Admin-only views verify user is team admin before allowing modifications
- **Public views**: Display only calculated scores, never expose admin-only data
- **Template escaping**: Django auto-escapes user content to prevent XSS
- **Email verification**: New users must verify their email address before accessing the platform
- **Token authentication**: API uses secure token-based authentication

## Technology Stack

- **Framework**: Django 5.2+
- **Database**: SQLite (development) / PostgreSQL (production)
- **ORM**: Django ORM only (no raw SQL)
- **API Framework**: Django REST Framework (for API endpoints)
- **Authentication**: Django's built-in auth + DRF Token Authentication
- **Static Files**: ManifestStaticFilesStorage (with content-based hashing for cache busting)
- **Environment**: django-environ for configuration
- **Frontend**: Responsive HTML/CSS with mobile-first design

## Configuration

Edit `.env` for local development:

```env
DEBUG=True
SECRET_KEY=your-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1

# For SQLite (default)
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=db.sqlite3

# Or for PostgreSQL
DB_ENGINE=django.db.backends.postgresql
DB_NAME=janki_db
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
```

## Development Commands

```bash
# Create new app
python manage.py startapp myapp

# Create migrations for model changes
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Collect static files (run after CSS/JS changes)
python manage.py collectstatic

# Run development server
python manage.py runserver

# Run on specific host/port
python manage.py runserver 0.0.0.0:8000

# Access Django shell
python manage.py shell

# Create superuser
python manage.py createsuperuser

# Run tests
python manage.py test

# Create API token for a user
python manage.py drf_create_token <username>
```

## Deployment

For production deployment:

1. Set `DEBUG=False` in `.env`
2. Use a strong `SECRET_KEY`
3. Configure `ALLOWED_HOSTS` properly
4. Use PostgreSQL database
5. Set up email backend for email verification
6. Collect static files: `python manage.py collectstatic`
7. Set up a production web server (Gunicorn)
8. Use a reverse proxy (Nginx)
9. Enable HTTPS with SSL certificates
10. Configure proper logging

See `DEPLOYMENT.md` for detailed deployment instructions.

## Mobile Support

The application is fully responsive and mobile-friendly:
- ✅ Team detail pages
- ✅ Standings pages with filterable columns
- ✅ Session submission forms
- ✅ Session history views
- ✅ Admin management pages

Mobile optimizations include:
- Responsive grid layouts that stack on small screens
- Hidden table columns on mobile (shows most critical data only)
- Touch-friendly buttons and form inputs
- Horizontal scrolling for wide tables
- Adaptive navigation

## Documentation

- `README.md` - This file (getting started, features, usage)
- `API_DOCUMENTATION.md` - REST API reference
- `API_QUICK_START.md` - Quick start guide for API usage
- `DEPLOYMENT.md` - Production deployment guide
- `INSTALLATION.md` - Detailed installation instructions
- `.github/copilot-instructions.md` - Development guidelines and coding conventions

## Contributing

Refer to `.github/copilot-instructions.md` for:
- Code style and conventions
- Architecture guidelines
- Django best practices
- Mahjong scoring rules implementation
- Testing requirements

## License

To be determined.
