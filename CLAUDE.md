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
i18n.py                         # Translation infrastructure — _() function and get_locale()
translations/
  da.json                       # Danish translations (English key → Danish value)
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

### Internationalization (i18n)

The app supports two languages: **English** (code language) and **Danish** (default for users). All user-facing text must be wrapped in the `_()` translation function.

#### How it works

- **`i18n.py`**: Contains the `_()` function and `get_locale()` helper. Loaded translations live in memory.
- **`translations/da.json`**: Flat JSON dictionary mapping English strings → Danish translations. English is the key, Danish is the value.
- **Language preference**: Stored in `session['lang']` and a `lang` cookie. Default is `da`. Switched via `POST /set-language`.
- **Language picker**: In the footer of `base.html` (bottom-left corner, DA | EN buttons).

#### Rules for writing translatable text

1. **Write all code in English.** The English string is the source of truth — it is both the code-level string and the fallback if no translation exists.
2. **Wrap every user-facing string in `_()`.**
   - In templates: `{{ _('Some text') }}`
   - In `app.py` (flash messages, etc.): `flash(_('Some message.'), 'error')`
3. **For strings with dynamic values**, use `.format()` on the translated string:
   - `flash(_('Added {} vacation day(s)!').format(count), 'success')`
   - In da.json: `"Added {} vacation day(s)!": "Tilføjet {} feriedag(e)!"`
4. **For mixed static + dynamic text in templates**, split into parts:
   - `{{ _('Holiday Period') }} {{ period_label }}`
5. **Add a Danish translation** for every new string in `translations/da.json`.
6. **Do NOT translate**: variable names, CSS classes, URLs, HTML attributes (except user-visible ones like `title` and `placeholder`), JavaScript internals, or brand names used as identifiers.
7. **Placeholders** like `placeholder="e.g., Christmas"` should also be wrapped: `placeholder="{{ _('e.g., Christmas') }}"`.

#### Adding a new translatable string

1. Write the English string in your code wrapped in `_()`.
2. Open `translations/da.json` and add a new entry: `"English text": "Danish text"`.
3. If you don't know the Danish translation, add the English string as the value — it will display in English until translated.

### Holiday Periods: Earning vs Spending

Each holiday year has two distinct periods:

- **Earning Period** (Optjeningsperiode): Sep 1 Year N → Aug 31 Year N+1. This is when holiday days accrue. Used to calculate how many days a user has earned so far.
- **Holiday Period / Spending Period** (Afholdelsesperiode): Jan 1 Year N+1 → Dec 31 Year N+1. This is when earned days can be used.

**"Holiday period" always means the spending period.** This is the one that matters for product owners and day-to-day use. The earning period exists in the background to power accrual calculations.

In the database (`holiday_periods` table):
- `start_date` / `end_date` = the **spending period** (Jan 1 – Dec 31)
- `earning_start` / `earning_end` = the **earning period** (Sep 1 – Aug 31)
- Periods are auto-generated on app startup by `db.ensure_periods_exist()` — not editable by admins

Public holidays (`period_holidays` table) are associated with a **spending period** via `period_id`. A holiday on May 14 2026 belongs to the 2025/2026 spending period (Jan 1 2026 – Dec 31 2026).

### Database Schema

- `team_members`: Stores team member names and emojis
- `vacation_days`: Stores vacation dates with foreign key to team_members
- `holiday_periods`: Holiday year definitions with earning and spending date ranges
- `period_holidays`: Public holidays per spending period (shared across all departments)
- `holidays`: Legacy table (unused — superseded by `period_holidays`)
- `events`: Stores events for team planning
- `event_responses`: Stores who is attending which event
- `users`: Authentication (shortname stored as `username`, hashed password, email, display_name, theme, role, accrued_days)
- `user_secondary_departments`: Many-to-many for users displayed as guests in additional departments
- `operation_log`: Audit log with nullable `user_id`, `operation_type` (e.g. `holiday_recalculation`, `setting_update`), and `message`
- `schema_migrations`: Tracks which migrations have been applied

### Styling — Børsen Brand

The UI follows the Børsen (borsen.dk) visual identity. Custom colors are defined in the Tailwind config in `base.html`:

| Token | Hex | Usage |
|---|---|---|
| `borsen-red` | `#c8102e` | Primary action buttons, active nav tabs |
| `borsen-red-dark` | `#a00d24` | Button hover states |
| `borsen-red-light` | `#fde8eb` | Light backgrounds for badges, active dropdown items |
| `borsen-pink` | `#db3d7f` | Vacation day indicators (calendar grid, bar charts, mini calendars) |
| `borsen-pink-dark` | `#c22e6a` | Pink hover/dark variant |
| `borsen-black` | `#1a1a1a` | Logo text color |
| `borsen-cream` | `#f5f0e8` | Page background (warm off-white) |
| `borsen-cream-dark` | `#e8e0d4` | Nav bars, card inner sections |

**Rules:**
- Both nav bars (secondary slim bar + primary nav) use `borsen-cream-dark` background with dark text — never black/dark backgrounds
- Action buttons use `borsen-red`, not Tailwind blue
- Vacation/holiday indicators use `borsen-pink`, not Tailwind blue
- Focus rings and interactive link text use `borsen-red`
- The `info` flash message keeps Tailwind blue (semantic color, not brand)
- All timestamps use Copenhagen timezone via `db._now()` — never MySQL `NOW()`

### Database Migrations

Migrations run automatically on app startup via `migrate.py`. They are tracked in the `schema_migrations` table. To add a schema change, create the next numbered `.sql` file in `migrations/` (e.g. `006_add_something.sql`). Keep migrations idempotent — the runner tolerates duplicate column errors (MySQL 1060).

**Important:** MySQL does not support `ADD COLUMN IF NOT EXISTS`. Plain `ALTER TABLE ... ADD COLUMN` is fine — the migration runner handles duplicate column errors gracefully.

**Important:** Do NOT use SQL comments (`--`) in migration files. The migration runner splits on `;` and does not strip comments, so a comment containing a semicolon will cause a syntax error.

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
