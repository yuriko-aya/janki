# Deployment Guide - Gunicorn

**Status:** ✅ **Gunicorn installed and tested**  
**Version:** 21.2.0  
**Last Updated:** December 26, 2025

---

## Quick Deployment Checklist

After pulling latest code to production:

1. **Activate virtual environment**
   ```bash
   cd /home/alice/lab/janki
   source env/bin/activate
   ```

2. **Install/Update dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run migrations**
   ```bash
   python manage.py migrate
   ```

4. **Collect static files**
   ```bash
   python manage.py collectstatic --noinput
   ```

5. **Restart Gunicorn**
   ```bash
   sudo systemctl restart janki
   # OR if using manual process:
   pkill -f gunicorn
   gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --daemon
   ```

6. **Check for errors**
   ```bash
   python manage.py check
   sudo journalctl -u janki -n 50  # If using systemd
   ```

---

## Recent Updates Requiring Migration

### December 26, 2025 - drf-multitokenauth Migration

**Changes:**
- Migrated from Knox to drf-multitokenauth for multi-token support
- Added public API endpoint `/api/teams/<slug>/exists/`

**Required on Production:**
```bash
# 1. Install new dependencies
pip install drf-multitokenauth==2.1.0 django-ipware==3.0.7

# 2. Run migrations (creates drf_multitokenauth_multitoken table)
python manage.py migrate

# 3. Restart application
sudo systemctl restart janki
```

**Migrations Applied:**
- `drf_multitokenauth.0001_initial`
- `drf_multitokenauth.0002_rename_ip_address_20160426`
- `drf_multitokenauth.0003_pk_migration`
- `drf_multitokenauth.0004_multitoken_name`

---

## Overview

Gunicorn is a production-ready WSGI HTTP server for Python applications. It has been added to the project for deployment.

## Installation

Gunicorn is already installed in the virtual environment.

### Verify Installation

```bash
source env/bin/activate
gunicorn --version
# Output: gunicorn (version 21.2.0)
```

### Install in New Environment

```bash
pip install -r requirements.txt
```

---

## Running with Gunicorn

### Basic Command

```bash
gunicorn config.wsgi:application
```

### With Specific Port

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

### Production Configuration

```bash
gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 4 \
  --worker-class sync \
  --timeout 30 \
  --access-logfile - \
  --error-logfile -
```

---

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `--bind` | 127.0.0.1:8000 | Server socket address |
| `--workers` | 1 | Number of worker processes |
| `--worker-class` | sync | Type of worker (sync, async, etc.) |
| `--timeout` | 30 | Worker timeout in seconds |
| `--access-logfile` | - | Access log file path (- for stdout) |
| `--error-logfile` | - | Error log file path (- for stderr) |

### Recommended Settings

For **development:**
```bash
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2
```

For **production:**
```bash
gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 4 \
  --worker-class sync \
  --max-requests 1000 \
  --timeout 30 \
  --access-logfile /var/log/gunicorn/access.log \
  --error-logfile /var/log/gunicorn/error.log \
  --log-level info
```

---

## Test Results

### Successful Boot
```
[2025-12-14 08:46:59 +0700] [118428] [INFO] Starting gunicorn 21.2.0
[2025-12-14 08:46:59 +0700] [118428] [INFO] Listening at: http://0.0.0.0:8000 (118428)
[2025-12-14 08:46:59 +0700] [118428] [INFO] Using worker: sync
[2025-12-14 08:46:59 +0700] [118429] [INFO] Booting worker with pid: 118429
[2025-12-14 08:46:59 +0700] [118430] [INFO] Booting worker with pid: 118430
```

✅ Gunicorn successfully starts and boots workers

---

## Using with Reverse Proxy (Nginx)

### Nginx Configuration Example

```nginx
upstream gunicorn {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name example.com;

    location / {
        proxy_pass http://gunicorn;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /path/to/project/static/;
    }
}
```

---

## Using with Systemd

### Service File: `/etc/systemd/system/janki.service`

```ini
[Unit]
Description=Janki Mahjong Tracker
After=network.target
Requires=postgresql.service

[Service]
Type=notify
User=alice
WorkingDirectory=/home/alice/lab/janki
Environment="PATH=/home/alice/lab/janki/env/bin"
ExecStart=/home/alice/lab/janki/env/bin/gunicorn \
    config.wsgi:application \
    --bind 127.0.0.1:8000 \
    --workers 4 \
    --timeout 30

Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

### Commands

```bash
# Start service
sudo systemctl start janki

# Stop service
sudo systemctl stop janki

# Restart service
sudo systemctl restart janki

# View status
sudo systemctl status janki

# View logs
sudo journalctl -u janki -f
```

---

## Performance Tuning

### Worker Count

- **Rule of thumb:** `(2 × CPU cores) + 1`
- **Example:** 4-core CPU → 9 workers
- **For single-core:** Start with 2-4 workers

### Timeout

- **Default:** 30 seconds
- **Increase for:** Long-running requests, large datasets
- **Decrease for:** Production stability (prevent hangs)

### Max Requests

- **Prevents memory leaks:** `--max-requests 1000`
- **Recycles workers:** After N requests
- **Recommended:** 1000-2000 for production

---

## Debugging

### Enable Debug Logging

```bash
gunicorn config.wsgi:application --log-level debug
```

### Check Worker Status

```bash
ps aux | grep gunicorn
```

### Common Issues

**Port already in use:**
```bash
lsof -i :8000
kill -9 <PID>
```

**Worker crashes:**
- Check error logs
- Increase `--timeout` value
- Check system memory

---

## Requirements

```
Django==5.2.8
django-environ==0.12.0
psycopg2-binary==2.9.11
djangorestframework==3.16.1
gunicorn==21.2.0
```

All dependencies are in `requirements.txt` ✅

