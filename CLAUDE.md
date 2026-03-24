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

## Running the Application

### Start Services
```bash
docker compose up --build
```

### Stop Services
```bash
docker compose down
```

### Stop and Remove Data
```bash
docker compose down -v
```

### Access the Application
- **Streamlit UI**: http://localhost:8501
- **MySQL**: localhost:3306

### Default Credentials
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
- `docker-compose.yml`: Service orchestration
- `Dockerfile`: Streamlit app container definition
- `requirements.txt`: Python dependencies
- `init.sql`: Database initialization script

### Managing Team Members

Team members can be added and deleted directly through the UI in the "Manage Team Members" section. Each member has a name and an emoji.

Alternatively, edit `init.sql` and rebuild containers, or manually insert into the database:
```sql
INSERT INTO team_members (name, emoji) VALUES ('New Member', '🎯');
```

### Database Access

Connect to MySQL container:
```bash
docker exec -it vacation_mysql mysql -u vacation_user -pvacation_pass vacation_db
```
