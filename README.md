# Team Planner

Team vacation planning application built with Flask, HTMX, and Tailwind CSS, backed by MySQL and running in Docker.

## Local development

### Prerequisites

- Docker & Docker Compose

### Getting started

```bash
make up
```

This builds and starts all containers. Once ready, the app is available at:

- **Web UI**: http://localhost:5000
- **MySQL**: localhost:3306

Run `make help` to see all available commands.

### Useful commands

```bash
make restart    # Restart all services
make logs       # Follow logs from all services
make logs-app   # Follow app logs only
make shell-app  # Open a shell in the app container
make shell-db   # Open a MySQL prompt
make clean      # Stop services and remove all data
```

### Login

The app requires authentication. Register a new account on the login screen, or use the default user created by the initial migration.

### Database migrations

Migrations run automatically on app startup. To run them manually:

```bash
make migrate
```

Migration files live in `migrations/` and are numbered sequentially (`001_initial.sql`, `002_add_users.sql`, etc.). To add a new migration, create the next numbered `.sql` file in that directory.

### Database credentials

| Key      | Value           |
|----------|-----------------|
| Host     | `localhost`     |
| Port     | `3306`          |
| Database | `vacation_db`   |
| User     | `vacation_user` |
| Password | `vacation_pass` |

## Deployment

The application is deployed as Docker containers via Docker Compose. The same `docker-compose.yml` is used for both local development and deployment.

The stack consists of two services:

- **web** - Python 3.11 slim image running Flask via Gunicorn
- **mysql** - MySQL 8.0 with a persistent volume for data storage

The database is initialised automatically from `init.sql` on first start.
