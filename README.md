# Mahjong Score Tracker

A Django web application for tracking Mahjong scores across multiple teams.

## Features

- **Multi-team support**: Multiple teams can be managed independently
- **Score tracking**: Record individual scores for each player in Mahjong sessions
- **Standings**: View team rankings with aggregated scores
- **Admin dashboard**: Team admins can manage members and submit scores
- **Public pages**: View-only access to team information and standings

## Project Structure

```
project_root/
├── accounts/           # User authentication, TeamAdmin model
├── teams/              # Team and Member models
├── scores/             # RawScore, CalculatedScore, and scoring logic
│   └── services/
│       └── calculator.py   # Score aggregation and validation
├── templates/          # HTML templates organized by app
├── static/             # CSS, JavaScript, images
├── config/             # Django settings and URL configuration
├── manage.py
├── requirements.txt
├── .env               # Environment variables (local development)
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
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
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

7. **Start the development server**
   ```bash
   python manage.py runserver
   ```

8. **Access the application**
   - Main site: http://localhost:8000
   - Admin panel: http://localhost:8000/admin
   - Teams: http://localhost:8000/teams/

## Usage

### Creating a Team

1. Login to the admin panel with your superuser account
2. Navigate to Teams → Create Team
3. Enter the team name and click Create
4. You are now the admin of this team

### Adding Members

1. Go to your team's detail page
2. Click "Manage Members"
3. Click "+ Add Member" and enter member names

### Submitting Scores

1. From the Members page, click "Submit Session"
2. Enter a unique Session ID (e.g., "2025-01-15-game1")
3. Select each of the 4 players and enter their scores
4. Click "Submit Session"
5. Scores are automatically aggregated for each player

### Viewing Standings

1. Navigate to any team's page
2. Click "Standings" to see player rankings
3. Standings are public (no login required)

## Models

### Team
- `name`: Team name
- `slug`: URL-friendly identifier
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp

### Member
- `team`: ForeignKey to Team
- `name`: Member name
- `join_date`: Date member joined
- `created_at`: Creation timestamp

### RawScore
- `member`: ForeignKey to Member
- `score`: Integer score value
- `session_id`: Groups 4 scores per session
- `created_at`: Creation timestamp

### CalculatedScore
- `member`: OneToOneField to Member
- `total`: Sum of all RawScores
- `games_played`: Number of unique sessions
- `average_per_game`: Average score per game
- `updated_at`: Last update timestamp

## Architecture

### Data Flow

1. **Score Submission**: Team admin submits 4 scores for a session
2. **Validation**: System validates exactly 4 scores per session per team
3. **Storage**: Scores stored as RawScore objects
4. **Aggregation**: CalculatedScore automatically updated for each member
5. **Display**: Public pages show aggregated CalculatedScores only

### Service Layer

Business logic is centralized in `scores/services/calculator.py`:
- `validate_session_complete()`: Ensures 4 scores per session
- `recalculate_member_score()`: Updates CalculatedScore
- `get_team_standings()`: Returns ranked members
- `submit_session_scores()`: Atomic score submission

### Security

- **Team isolation**: All queries filtered by team to prevent cross-team access
- **Permission checks**: Admin-only views verify user is team admin
- **Public views**: Display only calculated scores, never raw scores
- **Template escaping**: Django auto-escapes user content

## Technology Stack

- **Framework**: Django 5.2+
- **Database**: SQLite (development) / PostgreSQL (recommended for production)
- **ORM**: Django ORM only
- **API Framework**: Django REST Framework (optional)
- **Environment**: django-environ for configuration

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

# Run development server
python manage.py runserver

# Access Django shell
python manage.py shell

# Create superuser
python manage.py createsuperuser

# Run tests
python manage.py test
```

## Deployment

For production deployment:

1. Set `DEBUG=False` in `.env`
2. Use a strong `SECRET_KEY`
3. Configure `ALLOWED_HOSTS` properly
4. Use PostgreSQL database
5. Set up a production web server (Gunicorn, uWSGI)
6. Use a reverse proxy (Nginx, Apache)
7. Enable HTTPS
8. Configure static files serving

## Contributing

Refer to `.github/copilot-instructions.md` for development guidelines and code style conventions.

## License

To be determined.
