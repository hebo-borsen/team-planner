# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Team vacation planning application with Streamlit frontend, running in Docker with Docker Compose and MySQL database.

## Architecture

- **Streamlit App** (`app.py`): Frontend UI for vacation management
- **MySQL Database**: Stores team members and vacation days
- **Docker Compose**: Orchestrates both services with health checks

### Database Schema

- `team_members`: Stores team member names and emojis
- `vacation_days`: Stores vacation dates with foreign key to team_members
- `holidays`: Stores public holidays with date and name
- `events`: Stores events for team planning
- `event_responses`: Stores who is attending which event
- `users`: Authentication (username + SHA-256 hashed password)
- `schema_migrations`: Tracks which migrations have been applied

## Running the Application

Use `make help` to see all commands. Key ones:

```bash
make up        # Start all services
make down      # Stop all services
make restart   # Restart all services
make migrate   # Run pending database migrations
make clean     # Stop and remove all data
```

### Access the Application
- **Streamlit UI**: http://localhost:8501
- **MySQL**: localhost:3306

### Default Credentials
- **App login**: `hebo` / `hebo` (forced password change on first login)
- MySQL Root Password: `rootpassword`
- MySQL User: `vacation_user`
- MySQL Password: `vacation_pass`
- Database Name: `vacation_db`

## Features

### UI Structure
- **Sidebar**: Add vacations for team members (primary action)
- **Tab 1 - Calendar**: View vacation calendar with month/year selector, export to Excel
- **Tab 2 - Holidays**: Add and delete holidays
- **Tab 3 - Team Members**: Add and delete team members with custom emojis
- **Tab 4 - Event Planning**: Create events, track attendance, share direct links

### Core Functionality
- Create and manage team members with custom name and emoji (50+ emoji options)
- Select team member from dropdown (displays with emoji)
- Add single vacation days or date ranges
- Add public holidays with names (single day or date range)
- View calendar with holidays (green), vacations (blue), and weekends (light grey)
- Month/year selector to navigate calendar
- Export vacation schedule to Excel
- Delete vacation days, holidays, and team members

## Development

### File Structure
- `app.py`: Main Streamlit application
- `migrate.py`: Database migration runner
- `migrations/`: Numbered SQL migration files
- `docker-compose.yml`: Service orchestration
- `Dockerfile`: Streamlit app container definition
- `requirements.txt`: Python dependencies
- `init.sql`: Database initialization script (legacy, kept for fresh volumes)

### Database Migrations

Migrations run automatically on app startup via `migrate.py`. They are tracked in the `schema_migrations` table. To add a schema change, create the next numbered `.sql` file in `migrations/` (e.g. `003_add_something.sql`). Use `IF NOT EXISTS` / `ON DUPLICATE KEY` to keep migrations idempotent.

### Managing Team Members

Team members can be added and deleted directly through the UI in the "Manage Team Members" section. Each member has a name and an emoji.

### Database Access

Connect to MySQL container:
```bash
docker exec -it vacation_mysql mysql -u vacation_user -pvacation_pass vacation_db
```
