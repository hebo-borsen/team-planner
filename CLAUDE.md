# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Team vacation planning application built with Flask + HTMX + Tailwind CSS, running in Docker with Docker Compose and MySQL database.

## Architecture

- **Flask App** (`app.py`): All routes, auth decorators, and request handling in a single file
- **Database layer** (`db.py`): All database queries in one place
- **Templates** (`templates/`): Jinja2 templates with Tailwind CSS styling
- **Partials** (`templates/partials/`): HTMX partial templates for dynamic updates
- **MySQL Database**: Stores all persistent data
- **Docker Compose**: Orchestrates both services with health checks

### File Structure

```
app.py                          # Flask app — all routes, auth decorators
db.py                           # All database functions (auth, vacations, holidays, events, operation log)
migrate.py                      # Database migration runner
migrations/                     # Numbered SQL migration files
templates/
  base.html                     # Base layout: nav, Tailwind CDN, HTMX CDN, dark mode, flash messages
  login.html                    # Login form
  register.html                 # Registration form
  force_password.html           # Forced password change
  calendar.html                 # Vacation calendar (home page)
  holidays.html                 # Holiday management
  events.html                   # Event list + RSVP
  event_detail.html             # Single event view (share page)
  profile.html                  # Profile + password change
  partials/
    _calendar_grid.html         # Calendar table (HTMX: month/year switch)
    _holiday_list.html          # Holiday list (HTMX: add/delete)
    _event_responses.html       # RSVP section (HTMX: toggle)
```

### Key Conventions

- **`app.py` contains all routes.** This is a small app (~15 routes), no blueprints needed.
- **`db.py` owns all SQL.** Routes call functions from `db.py` — they never create their own database connections.
- **Templates extend `base.html`.** Auth pages (login, register, force_password) override the `nav` block to hide the nav bar.
- **Partials are for HTMX.** Files in `templates/partials/` are returned by HTMX endpoints and do NOT extend `base.html`.
- **HTMX for interactive updates.** Delete buttons, RSVP toggles, and calendar navigation use HTMX. Form submissions use standard POST-redirect-GET.
- **Keep imports at the top** of each file, to keep the code clean and readable.
- **Date format is `1. feb - 2026`**. All user-facing dates use the `|fmtdate` Jinja2 filter (e.g. `{{ date|fmtdate }}`). For dates with time, use `|fmtdatetime` (e.g. `1. feb - 2026 14:30`). HTML `<input type="date">` values must stay in ISO format (required by browsers).

### Database Schema

- `team_members`: Stores team member names and emojis
- `vacation_days`: Stores vacation dates with foreign key to team_members
- `holidays`: Stores public holidays with date and name
- `events`: Stores events for team planning
- `event_responses`: Stores who is attending which event
- `users`: Authentication (shortname stored as `username`, hashed password, email, display_name, theme, role, accrued_days)
- `operation_log`: Audit log with nullable `user_id`, `operation_type` (e.g. `holiday_recalculation`, `setting_update`), and `message`
- `schema_migrations`: Tracks which migrations have been applied

### Database Migrations

Migrations run automatically on app startup via `migrate.py`. They are tracked in the `schema_migrations` table. To add a schema change, create the next numbered `.sql` file in `migrations/` (e.g. `006_add_something.sql`). Keep migrations idempotent — the runner tolerates duplicate column errors (MySQL 1060).

**Important:** MySQL does not support `ADD COLUMN IF NOT EXISTS`. Plain `ALTER TABLE ... ADD COLUMN` is fine — the migration runner handles duplicate column errors gracefully.

## Running the Application

Use `make help` to see all commands. Key ones:

```bash
make up        # Start all services
make down      # Stop all services
make restart   # Restart all services
make migrate   # Run pending database migrations
make clean           # Stop and remove all data
make nuclear-restart # Wipe database, rebuild, and start fresh
```

### Access the Application
- **Web UI**: http://localhost:5000
- **MySQL**: localhost:3306

### Default Credentials
- **App login**: Register at `/register` — the first user created automatically becomes admin
- MySQL Root Password: `rootpassword`
- MySQL User: `vacation_user`
- MySQL Password: `vacation_pass`
- Database Name: `vacation_db`

### Database Access

Connect to MySQL container:
```bash
docker exec -it vacation_mysql mysql -u vacation_user -pvacation_pass vacation_db
```
