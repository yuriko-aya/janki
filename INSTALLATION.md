# Quick Start Guide

## Installation & Running

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Apply database migrations
```bash
python manage.py migrate
```

### 3. Create superuser (admin account)
```bash
python manage.py createsuperuser
# Follow prompts to create admin user
```

### 4. Start development server
```bash
python manage.py runserver
```

### 5. Access the application
- **Main site:** http://localhost:8000/teams/
- **Admin panel:** http://localhost:8000/admin
- Login with the superuser credentials created in step 3

---

## Quick Demo

1. Login to admin panel (http://localhost:8000/admin)
2. Go to Teams → Create Team
3. Enter team name and create
4. Go to team detail page → Manage Members
5. Add 4 or more members
6. Go back to Members page → Submit Session
7. Enter scores for 4 players
8. View standings

---

## Key Files

- `manage.py` - Django management script
- `requirements.txt` - Python dependencies
- `.env` - Environment configuration
- `config/settings.py` - Django settings
- `config/urls.py` - URL routing
- `*/models.py` - Database models
- `*/views.py` - View logic
- `*/urls.py` - App URL routing
- `templates/` - HTML templates

---

## Troubleshooting

### Port already in use
```bash
python manage.py runserver 8001
```

### Reset database
```bash
rm db.sqlite3
python manage.py migrate
python manage.py createsuperuser
```

### Clear cache
```bash
python manage.py clear_cache  # if cache configured
```

For more details, see README.md
