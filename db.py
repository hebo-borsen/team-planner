import mysql.connector
from mysql.connector import pooling
import hashlib
import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os

TZ = ZoneInfo('Europe/Copenhagen')


def _now():
    return datetime.now(TZ).replace(tzinfo=None)

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'database': os.getenv('DB_NAME', 'vacation_db'),
    'user': os.getenv('DB_USER', 'vacation_user'),
    'password': os.getenv('DB_PASSWORD', 'vacation_pass')
}

_pool = pooling.MySQLConnectionPool(pool_name="app", pool_size=int(os.getenv('DB_POOL_SIZE', 30)), **DB_CONFIG)


def get_db_connection():
    return _pool.get_connection()


def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def authenticate_user(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, must_change_password, theme, role, initials, font, email FROM users WHERE (username = %s OR LOWER(email) = LOWER(%s)) AND password_hash = %s",
        (username, username, hash_password(password))
    )
    user = cursor.fetchone()
    if user:
        cursor.execute("UPDATE users SET last_login = %s WHERE id = %s", (_now(), user[0]))
        conn.commit()
    cursor.close()
    conn.close()
    return user


def register_user(username, password, display_name=None, email=None, font=None, department_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM users")
        is_first = cursor.fetchone()[0] == 0
        is_pre_admin = False
        if email and not is_first:
            cursor.execute("SELECT COUNT(*) FROM pre_admins WHERE email = %s", (email.lower(),))
            is_pre_admin = cursor.fetchone()[0] > 0
        role = 'admin' if (is_first or is_pre_admin) else 'user'
        cursor.execute(
            "INSERT INTO users (username, password_hash, must_change_password, initials, display_name, email, font, role, department_id) VALUES (%s, %s, FALSE, %s, %s, %s, %s, %s, %s)",
            (username, hash_password(password), username, display_name, email, font, role, department_id)
        )
        new_id = cursor.lastrowid
        conn.commit()
        return True, "Account created! You can now log in.", new_id, role
    except mysql.connector.IntegrityError:
        return False, "Shortname already exists.", None, None
    finally:
        cursor.close()
        conn.close()


def update_password(user_id, new_password):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET password_hash = %s, must_change_password = FALSE WHERE id = %s",
        (hash_password(new_password), user_id)
    )
    conn.commit()
    cursor.close()
    conn.close()


def get_user_profile(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, email, display_name, theme, initials, font FROM users WHERE id = %s", (user_id,))
    profile = cursor.fetchone()
    cursor.close()
    conn.close()
    return profile


def update_user_profile(user_id, email, display_name, initials, font=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET email = %s, display_name = %s, initials = %s, font = %s WHERE id = %s",
        (email, display_name, initials, font, user_id)
    )
    conn.commit()
    cursor.close()
    conn.close()


def update_user_theme(user_id, theme):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET theme = %s WHERE id = %s", (theme, user_id))
    conn.commit()
    cursor.close()
    conn.close()


def create_session_token(user_id):
    token = secrets.token_hex(32)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET session_token = %s WHERE id = %s", (token, user_id))
    conn.commit()
    cursor.close()
    conn.close()
    return token


def get_user_by_session_token(token):
    if not token:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, must_change_password, theme, role, initials, font, email FROM users WHERE session_token = %s",
        (token,)
    )
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return user


def clear_session_token(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET session_token = NULL WHERE id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()


def get_all_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.username, u.display_name, u.email, u.role,
               u.days_off_per_year, u.start_date, u.active, u.department_id
        FROM users u
        ORDER BY u.active DESC, u.username
    """)
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return users


def set_user_role(user_id, role):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET role = %s WHERE id = %s", (role, user_id))
    conn.commit()
    cursor.close()
    conn.close()


def toggle_user_active(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET active = NOT active WHERE id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()


def update_display_name(user_id, display_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET display_name = %s WHERE id = %s", (display_name, user_id))
    conn.commit()
    cursor.close()
    conn.close()


def update_start_date(user_id, start_date):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET start_date = %s WHERE id = %s", (start_date, user_id))
    conn.commit()
    cursor.close()
    conn.close()


def update_days_off(user_id, days_off):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET days_off_per_year = %s WHERE id = %s", (days_off, user_id))
    conn.commit()
    cursor.close()
    conn.close()


def _prorate_entitlement(days_off_per_year, start_date, earning_start, earning_end):
    """If start_date is within the earning period, prorate. Otherwise full entitlement."""
    base = float(days_off_per_year)
    if start_date and earning_start <= start_date <= earning_end:
        months_in_period = (earning_end.year - start_date.year) * 12 + earning_end.month - start_date.month + 1
        if months_in_period < 1:
            months_in_period = 1
        return round(base / 12 * months_in_period, 1)
    return base


def get_vacation_summary(user_id, period_start, period_end, earning_start=None, earning_end=None):
    from datetime import date as _date
    earn_start = earning_start or period_start
    earn_end = earning_end or period_end
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT days_off_per_year, start_date FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    base_days = row[0] if row and row[0] is not None else 34
    user_start = row[1] if row else None
    entitlement = _prorate_entitlement(base_days, user_start, earn_start, earn_end)

    cursor.execute("""
        SELECT COUNT(*) FROM vacation_days vd
        JOIN team_members tm ON vd.member_id = tm.id
        JOIN users u ON u.username = tm.name
        WHERE u.id = %s AND vd.status = 'approved'
          AND vd.self_paid = FALSE
          AND vd.vacation_date BETWEEN %s AND %s
    """, (user_id, period_start, period_end))
    used = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    # Calculate accrued dynamically based on earning period
    today = _date.today()
    accrual_start = max(earn_start, user_start) if user_start and user_start > earn_start else earn_start
    months_elapsed = (today.year - accrual_start.year) * 12 + today.month - accrual_start.month
    if months_elapsed < 0:
        months_elapsed = 0
    accrued = round(float(base_days) / 12 * months_elapsed, 1)

    return {
        'days_off_per_year': entitlement,
        'used': used,
        'remaining': entitlement - used,
        'accrued': accrued,
        'accrual_start': accrual_start,
        'months_elapsed': months_elapsed,
        'base_days': float(base_days),
    }


def get_period_vacation_summary(user_id, period_start, period_end, earning_start=None, earning_end=None):
    earn_start = earning_start or period_start
    earn_end = earning_end or period_end
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT days_off_per_year, start_date FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    base_days = row[0] if row and row[0] is not None else 34
    user_start = row[1] if row else None
    entitlement = _prorate_entitlement(base_days, user_start, earn_start, earn_end)

    cursor.execute("""
        SELECT COUNT(*) FROM vacation_days vd
        JOIN team_members tm ON vd.member_id = tm.id
        JOIN users u ON u.username = tm.name
        WHERE u.id = %s AND vd.status = 'approved'
          AND vd.self_paid = FALSE
          AND vd.vacation_date BETWEEN %s AND %s
    """, (user_id, period_start, period_end))
    used = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    return {
        'days_off_per_year': entitlement,
        'used': used,
        'remaining': entitlement - used,
    }


def get_all_users_period_summary(period_start, period_end, department_id=None, earning_start=None, earning_end=None):
    earn_start = earning_start or period_start
    earn_end = earning_end or period_end
    conn = get_db_connection()
    cursor = conn.cursor()
    if department_id is not None:
        cursor.execute("""
            SELECT u.id, COALESCE(u.display_name, u.username) AS display_name,
                   u.days_off_per_year, u.start_date,
                   COALESCE(SUM(CASE WHEN vd.status = 'approved' AND vd.self_paid = FALSE THEN 1 ELSE 0 END), 0) AS used,
                   u.last_login
            FROM users u
            LEFT JOIN team_members tm ON tm.name = u.username
            LEFT JOIN vacation_days vd ON tm.id = vd.member_id
                AND vd.vacation_date BETWEEN %s AND %s
            WHERE u.active = TRUE AND u.department_id = %s
            GROUP BY u.id, u.display_name, u.username, u.days_off_per_year, u.start_date, u.last_login
            ORDER BY COALESCE(u.display_name, u.username)
        """, (period_start, period_end, department_id))
    else:
        cursor.execute("""
            SELECT u.id, COALESCE(u.display_name, u.username) AS display_name,
                   u.days_off_per_year, u.start_date,
                   COALESCE(SUM(CASE WHEN vd.status = 'approved' AND vd.self_paid = FALSE THEN 1 ELSE 0 END), 0) AS used,
                   u.last_login
            FROM users u
            LEFT JOIN team_members tm ON tm.name = u.username
            LEFT JOIN vacation_days vd ON tm.id = vd.member_id
                AND vd.vacation_date BETWEEN %s AND %s
            WHERE u.active = TRUE
            GROUP BY u.id, u.display_name, u.username, u.days_off_per_year, u.start_date, u.last_login
            ORDER BY COALESCE(u.display_name, u.username)
        """, (period_start, period_end))
    raw = cursor.fetchall()
    cursor.close()
    conn.close()
    from datetime import date as _date
    today = _date.today()
    results = []
    for uid, display_name, base_days, user_start, used, last_login in raw:
        base = base_days if base_days is not None else 34
        entitlement = _prorate_entitlement(base, user_start, earn_start, earn_end)
        accrual_start = max(earn_start, user_start) if user_start and user_start > earn_start else earn_start
        months_elapsed = (today.year - accrual_start.year) * 12 + today.month - accrual_start.month
        if months_elapsed < 0:
            months_elapsed = 0
        accrued = round(float(base) / 12 * months_elapsed, 1)
        available = round(accrued - int(used), 1)
        results.append((uid, display_name, entitlement, int(used), last_login, available))
    return results


# ---------------------------------------------------------------------------
# Operation log
# ---------------------------------------------------------------------------

def insert_operation_log(user_id, operation_type, message):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO operation_log (user_id, operation_type, message) VALUES (%s, %s, %s)",
        (user_id, operation_type, message)
    )
    conn.commit()
    cursor.close()
    conn.close()


def get_all_users_basic():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username FROM users ORDER BY username")
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return users


def needs_initial_accrued(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT accrued_days_initial FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row and not row[0]


def set_initial_accrued(user_id, days_used, period_start, start_date=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET accrued_days_initial = TRUE, start_date = %s WHERE id = %s",
        (start_date, user_id))
    conn.commit()
    cursor.close()
    conn.close()
    if days_used > 0 and period_start:
        backfill_vacation_days(user_id, int(days_used), period_start)


def backfill_vacation_days(user_id, count, period_start):
    """Insert `count` approved vacation days starting from period_start, skipping weekends/holidays."""
    from datetime import timedelta as td
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        conn.close()
        return
    username = row[0]
    cursor.execute("SELECT id FROM team_members WHERE name = %s", (username,))
    row = cursor.fetchone()
    if row:
        member_id = row[0]
    else:
        cursor.execute("INSERT INTO team_members (name, emoji) VALUES (%s, %s)", (username, '👤'))
        conn.commit()
        member_id = cursor.lastrowid
    # Fetch all enabled holidays in a generous range
    far_end = period_start + td(days=365)
    cursor.execute(
        "SELECT holiday_date FROM period_holidays WHERE enabled = TRUE AND holiday_date BETWEEN %s AND %s",
        (period_start, far_end))
    holidays = {r[0] for r in cursor.fetchall()}
    added = 0
    current = period_start
    while added < count:
        if current.weekday() not in (5, 6) and current not in holidays:
            try:
                cursor.execute(
                    """INSERT INTO vacation_days
                       (member_id, vacation_date, status, requested_by, approved_by, approved_at)
                       VALUES (%s, %s, 'approved', %s, %s, %s)""",
                    (member_id, current, user_id, user_id, _now()))
                added += 1
            except mysql.connector.IntegrityError:
                pass  # already exists, still counts
                added += 1
        current += td(days=1)
    conn.commit()
    cursor.close()
    conn.close()


def get_operation_log(limit=100, user_id=None, operation_type=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT ol.id, ol.user_id, u.username, ol.operation_type, ol.message, ol.created_at
        FROM operation_log ol
        LEFT JOIN users u ON ol.user_id = u.id
        WHERE 1=1
    """
    params = []
    if user_id is not None:
        query += " AND ol.user_id = %s"
        params.append(user_id)
    if operation_type is not None:
        query += " AND ol.operation_type = %s"
        params.append(operation_type)
    query += " ORDER BY ol.created_at DESC LIMIT %s"
    params.append(limit)
    cursor.execute(query, params)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# Team members
# ---------------------------------------------------------------------------

def get_team_members():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, emoji FROM team_members ORDER BY name")
    members = cursor.fetchall()
    cursor.close()
    conn.close()
    return members


def add_team_member(name, emoji):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO team_members (name, emoji) VALUES (%s, %s)", (name, emoji))
        conn.commit()
        return True, "Team member added successfully!"
    except mysql.connector.IntegrityError:
        return False, "A team member with this name already exists."
    finally:
        cursor.close()
        conn.close()


def delete_team_member(member_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM team_members WHERE id = %s", (member_id,))
    conn.commit()
    cursor.close()
    conn.close()


# ---------------------------------------------------------------------------
# Vacations
# ---------------------------------------------------------------------------

def add_vacation_for_user(user_id, start_date, end_date, requested_by=None, self_paid=False):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        conn.close()
        return 0, 0
    username = row[0]
    cursor.execute("SELECT id FROM team_members WHERE name = %s", (username,))
    row = cursor.fetchone()
    if row:
        member_id = row[0]
    else:
        cursor.execute("INSERT INTO team_members (name, emoji) VALUES (%s, %s)", (username, '👤'))
        conn.commit()
        member_id = cursor.lastrowid
    status = 'approved'
    cursor.execute(
        "SELECT holiday_date FROM period_holidays WHERE enabled = TRUE AND holiday_date BETWEEN %s AND %s",
        (start_date, end_date)
    )
    holidays = {row[0] for row in cursor.fetchall()}
    added = 0
    skipped = 0
    current = start_date
    while current <= end_date:
        if current.weekday() in (5, 6) or current in holidays:
            current += timedelta(days=1)
            continue
        try:
            cursor.execute(
                """INSERT INTO vacation_days
                   (member_id, vacation_date, status, requested_by, approved_by, approved_at, self_paid)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (member_id, current, status, requested_by,
                 requested_by, _now(), self_paid)
            )
            added += 1
        except mysql.connector.IntegrityError:
            skipped += 1
        current += timedelta(days=1)
    conn.commit()
    cursor.close()
    conn.close()
    return added, skipped


def add_vacation_day(member_id, vacation_date):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO vacation_days (member_id, vacation_date) VALUES (%s, %s)",
            (member_id, vacation_date)
        )
        conn.commit()
        return True, "Vacation day added successfully!"
    except mysql.connector.IntegrityError:
        return False, "This vacation day already exists."
    finally:
        cursor.close()
        conn.close()


def add_vacation_range(member_id, start_date, end_date):
    conn = get_db_connection()
    cursor = conn.cursor()
    current_date = start_date
    added_count = 0
    skipped_count = 0
    while current_date <= end_date:
        try:
            cursor.execute(
                "INSERT INTO vacation_days (member_id, vacation_date) VALUES (%s, %s)",
                (member_id, current_date)
            )
            added_count += 1
        except mysql.connector.IntegrityError:
            skipped_count += 1
        current_date += timedelta(days=1)
    conn.commit()
    cursor.close()
    conn.close()
    return added_count, skipped_count


def get_vacation_count():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM vacation_days WHERE status = 'approved'")
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return count


def get_all_vacations():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT tm.name as member_name, vd.vacation_date, vd.id, vd.status
        FROM vacation_days vd JOIN team_members tm ON vd.member_id = tm.id
        ORDER BY vd.vacation_date DESC, tm.name
    """)
    vacations = cursor.fetchall()
    cursor.close()
    conn.close()
    return vacations


def get_vacations_for_month(year, month):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT tm.id, tm.name as member_name, vd.vacation_date
        FROM team_members tm
        LEFT JOIN vacation_days vd ON tm.id = vd.member_id
            AND YEAR(vd.vacation_date) = %s AND MONTH(vd.vacation_date) = %s
        ORDER BY tm.name, vd.vacation_date
    """, (year, month))
    vacations = cursor.fetchall()
    cursor.close()
    conn.close()
    return vacations


def delete_vacation(vacation_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vacation_days WHERE id = %s", (vacation_id,))
    conn.commit()
    cursor.close()
    conn.close()




def get_user_vacations_grouped(user_id):
    """Group a user's vacations into consecutive periods by created_at."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT vd.id, vd.vacation_date, vd.created_at,
               COALESCE(creator.display_name, vd.requested_by) AS created_by_name
        FROM vacation_days vd
        JOIN team_members tm ON vd.member_id = tm.id
        JOIN users u ON u.username = tm.name
        LEFT JOIN users creator ON creator.username = vd.requested_by
        WHERE u.id = %s
        ORDER BY vd.created_at, vd.vacation_date
    """, (user_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    groups = []
    current = None
    for vid, vdate, created_at, created_by_name in rows:
        if current and current['created_at'] == created_at:
            current['ids'].append(vid)
            current['dates'].append(vdate)
            current['end_date'] = vdate
            current['count'] += 1
        else:
            if current:
                groups.append(current)
            current = {
                'ids': [vid],
                'dates': [vdate],
                'start_date': vdate,
                'end_date': vdate,
                'created_at': created_at,
                'created_by': created_by_name,
                'count': 1,
            }
    if current:
        groups.append(current)

    # Sort by start_date so periods appear chronologically
    groups.sort(key=lambda g: g['start_date'])
    return groups


def delete_vacation_bulk(ids):
    """Delete multiple vacation days (admin use)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    fmt = ','.join(['%s'] * len(ids))
    cursor.execute(f"DELETE FROM vacation_days WHERE id IN ({fmt})", tuple(ids))
    deleted = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    return deleted


def get_vacation_ids_for_user_dates(user_id, start_date, end_date, statuses=None):
    """Return vacation_day IDs for a user within a date range, optionally filtered by status."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if statuses:
        fmt = ','.join(['%s'] * len(statuses))
        cursor.execute(f"""
            SELECT vd.id FROM vacation_days vd
            JOIN team_members tm ON vd.member_id = tm.id
            JOIN users u ON u.username = tm.name
            WHERE u.id = %s AND vd.vacation_date BETWEEN %s AND %s
              AND vd.status IN ({fmt})
            ORDER BY vd.vacation_date
        """, (user_id, start_date, end_date) + tuple(statuses))
    else:
        cursor.execute("""
            SELECT vd.id FROM vacation_days vd
            JOIN team_members tm ON vd.member_id = tm.id
            JOIN users u ON u.username = tm.name
            WHERE u.id = %s AND vd.vacation_date BETWEEN %s AND %s
            ORDER BY vd.vacation_date
        """, (user_id, start_date, end_date))
    ids = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return ids



# ---------------------------------------------------------------------------
# Holidays
# ---------------------------------------------------------------------------

def add_holiday(holiday_date, holiday_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO holidays (holiday_date, holiday_name) VALUES (%s, %s)",
            (holiday_date, holiday_name)
        )
        conn.commit()
        return True, "Holiday added successfully!"
    except mysql.connector.IntegrityError:
        return False, "This holiday date already exists."
    finally:
        cursor.close()
        conn.close()


def add_holiday_range(start_date, end_date, holiday_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    current_date = start_date
    added_count = 0
    skipped_count = 0
    while current_date <= end_date:
        try:
            cursor.execute(
                "INSERT INTO holidays (holiday_date, holiday_name) VALUES (%s, %s)",
                (current_date, holiday_name)
            )
            added_count += 1
        except mysql.connector.IntegrityError:
            skipped_count += 1
        current_date += timedelta(days=1)
    conn.commit()
    cursor.close()
    conn.close()
    return added_count, skipped_count


def get_holidays_for_month(year, month):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT holiday_date, holiday_name, id FROM holidays
        WHERE YEAR(holiday_date) = %s AND MONTH(holiday_date) = %s
        ORDER BY holiday_date
    """, (year, month))
    holidays = cursor.fetchall()
    cursor.close()
    conn.close()
    return holidays


def get_all_holidays():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT holiday_date, holiday_name, id FROM holidays ORDER BY holiday_date DESC")
    holidays = cursor.fetchall()
    cursor.close()
    conn.close()
    return holidays


def delete_holiday(holiday_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM holidays WHERE id = %s", (holiday_id,))
    conn.commit()
    cursor.close()
    conn.close()


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

def create_event(event_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO events (event_name) VALUES (%s)", (event_name,))
        conn.commit()
        return True, "Event created successfully!"
    except mysql.connector.Error as e:
        return False, f"Error creating event: {str(e)}"
    finally:
        cursor.close()
        conn.close()


def get_all_events():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, event_name, created_at FROM events ORDER BY created_at DESC")
    events = cursor.fetchall()
    cursor.close()
    conn.close()
    return events


def get_event_by_id(event_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, event_name, created_at FROM events WHERE id = %s", (event_id,))
    event = cursor.fetchone()
    cursor.close()
    conn.close()
    return event


def delete_event(event_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM events WHERE id = %s", (event_id,))
    conn.commit()
    cursor.close()
    conn.close()


def set_event_response(event_id, member_id, is_attending):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO event_responses (event_id, member_id, is_attending)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE is_attending = %s
        """, (event_id, member_id, is_attending, is_attending))
        conn.commit()
        return True
    except mysql.connector.Error as e:
        print(f"Error setting event response: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()


def get_all_users_for_calendar(department_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if department_id:
        cursor.execute("""
            SELECT u.id, u.username, u.display_name, u.initials, u.font,
                   u.department_id, d.name AS dept_name, 0 AS is_secondary
            FROM users u
            LEFT JOIN departments d ON u.department_id = d.id
            WHERE u.active = TRUE AND u.department_id = %s

            UNION

            SELECT u.id, u.username, u.display_name, u.initials, u.font,
                   u.department_id, d.name AS dept_name, 1 AS is_secondary
            FROM users u
            LEFT JOIN departments d ON u.department_id = d.id
            INNER JOIN user_secondary_departments usd ON u.id = usd.user_id AND usd.department_id = %s
            WHERE u.active = TRUE

            ORDER BY is_secondary, username
        """, (department_id, department_id))
    else:
        cursor.execute("""
            SELECT u.id, u.username, u.display_name, u.initials, u.font,
                   u.department_id, d.name AS dept_name, 0 AS is_secondary
            FROM users u
            LEFT JOIN departments d ON u.department_id = d.id
            WHERE u.active = TRUE
            ORDER BY d.sort_order, d.name, u.username
        """)
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return users


def get_vacations_for_date_range(start_date, end_date):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, COALESCE(u.display_name, u.username) as display,
               vd.vacation_date, vd.status,
               vd.created_at,
               COALESCE(creator.display_name, vd.requested_by) AS created_by_name,
               vd.self_paid
        FROM users u
        LEFT JOIN team_members tm ON tm.name = u.username
        LEFT JOIN vacation_days vd ON tm.id = vd.member_id
            AND vd.vacation_date BETWEEN %s AND %s
        LEFT JOIN users creator ON creator.username = vd.requested_by
        ORDER BY COALESCE(u.display_name, u.username), vd.vacation_date
    """, (start_date, end_date))
    vacations = cursor.fetchall()
    cursor.close()
    conn.close()
    return vacations


def get_all_enabled_holidays():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT holiday_date FROM period_holidays WHERE enabled = TRUE AND department_id IS NULL")
    holidays = {row[0] for row in cursor.fetchall()}
    cursor.close()
    conn.close()
    return holidays


def get_holidays_for_date_range(start_date, end_date):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT holiday_date, name, id FROM period_holidays
        WHERE enabled = TRUE AND department_id IS NULL AND holiday_date BETWEEN %s AND %s
        ORDER BY holiday_date
    """, (start_date, end_date))
    holidays = cursor.fetchall()
    cursor.close()
    conn.close()
    return holidays


# ---------------------------------------------------------------------------
# Holiday periods (settings)
# ---------------------------------------------------------------------------

def get_holiday_periods():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, label, start_date, end_date, earning_start, earning_end FROM holiday_periods ORDER BY start_date")
    periods = cursor.fetchall()
    cursor.close()
    conn.close()
    return periods


def get_current_period_id():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM holiday_periods
        WHERE start_date <= CURDATE() AND end_date >= CURDATE()
        LIMIT 1
    """)
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row[0] if row else None


def ensure_periods_exist():
    """Auto-generate holiday periods for current year ± 5 years."""
    from datetime import date as _date
    current_year = _date.today().year
    conn = get_db_connection()
    cursor = conn.cursor()
    for year in range(current_year - 2, current_year + 6):
        label = f"{year}/{year + 1}"
        earning_start = _date(year, 9, 1)
        earning_end = _date(year + 1, 8, 31)
        spending_start = _date(year + 1, 1, 1)
        spending_end = _date(year + 1, 12, 31)
        try:
            cursor.execute(
                "INSERT INTO holiday_periods (label, start_date, end_date, earning_start, earning_end) VALUES (%s, %s, %s, %s, %s)",
                (label, spending_start, spending_end, earning_start, earning_end))
        except mysql.connector.IntegrityError:
            pass
    conn.commit()
    cursor.close()
    conn.close()


def get_period_holidays(period_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, holiday_date, enabled FROM period_holidays
        WHERE period_id = %s AND department_id IS NULL ORDER BY holiday_date
    """, (period_id,))
    holidays = cursor.fetchall()
    cursor.close()
    conn.close()
    return holidays


def toggle_period_holiday(holiday_id):
    """Toggle enabled/disabled. Returns period_id."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT period_id, enabled FROM period_holidays WHERE id = %s", (holiday_id,))
    row = cursor.fetchone()
    if row:
        period_id, enabled = row
        cursor.execute("UPDATE period_holidays SET enabled = %s WHERE id = %s", (not enabled, holiday_id))
        conn.commit()
    else:
        period_id = None
    cursor.close()
    conn.close()
    return period_id


def update_period_holiday_name(holiday_id, new_name):
    """Update holiday name. Returns period_id."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT period_id FROM period_holidays WHERE id = %s", (holiday_id,))
    row = cursor.fetchone()
    if row:
        period_id = row[0]
        cursor.execute("UPDATE period_holidays SET name = %s WHERE id = %s", (new_name, holiday_id))
        conn.commit()
    else:
        period_id = None
    cursor.close()
    conn.close()
    return period_id


def update_period_holiday_date(holiday_id, new_date):
    """Update holiday date. Returns period_id."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT period_id FROM period_holidays WHERE id = %s", (holiday_id,))
    row = cursor.fetchone()
    if row:
        period_id = row[0]
        cursor.execute("UPDATE period_holidays SET holiday_date = %s WHERE id = %s", (new_date, holiday_id))
        conn.commit()
    else:
        period_id = None
    cursor.close()
    conn.close()
    return period_id


def add_period_holiday(period_id, name, holiday_date):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO period_holidays (period_id, name, holiday_date, enabled, department_id) VALUES (%s, %s, %s, TRUE, NULL)",
        (period_id, name, holiday_date))
    conn.commit()
    cursor.close()
    conn.close()


def generate_holidays_for_period(period_id, holidays_list):
    """Delete existing holidays for a period and insert from a list of (name, date) tuples."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM period_holidays WHERE period_id = %s", (period_id,))
    for name, hdate in holidays_list:
        cursor.execute(
            "INSERT INTO period_holidays (period_id, name, holiday_date, enabled, department_id) VALUES (%s, %s, %s, TRUE, NULL)",
            (period_id, name, hdate))
    conn.commit()
    cursor.close()
    conn.close()


def delete_period_holiday(holiday_id):
    """Delete a holiday. Returns period_id."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT period_id FROM period_holidays WHERE id = %s", (holiday_id,))
    row = cursor.fetchone()
    if row:
        period_id = row[0]
        cursor.execute("DELETE FROM period_holidays WHERE id = %s", (holiday_id,))
        conn.commit()
    else:
        period_id = None
    cursor.close()
    conn.close()
    return period_id


def get_event_responses(event_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT tm.id as member_id, tm.name as member_name, tm.emoji as member_emoji, er.is_attending
        FROM team_members tm
        LEFT JOIN event_responses er ON tm.id = er.member_id AND er.event_id = %s
        ORDER BY tm.name
    """, (event_id,))
    responses = cursor.fetchall()
    cursor.close()
    conn.close()
    return responses


# Review requests

def create_review_request(title, start_date, end_date, created_by, department_id, color='#f59e0b'):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO review_requests (title, start_date, end_date, created_by, department_id, color, active) VALUES (%s, %s, %s, %s, %s, %s, FALSE)",
        (title, start_date, end_date, created_by, department_id, color))
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return new_id


def get_all_review_requests(department_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if department_id is not None:
        cursor.execute("""
            SELECT rr.id, rr.title, rr.start_date, rr.end_date, rr.created_by, rr.active, rr.created_at,
                   COALESCE(u.display_name, u.username) AS creator_name,
                   rr.department_id, d.name AS dept_name, rr.color, rr.review_activated
            FROM review_requests rr
            LEFT JOIN users u ON u.id = rr.created_by
            LEFT JOIN departments d ON d.id = rr.department_id
            WHERE rr.department_id = %s
            ORDER BY rr.start_date ASC
        """, (department_id,))
    else:
        cursor.execute("""
            SELECT rr.id, rr.title, rr.start_date, rr.end_date, rr.created_by, rr.active, rr.created_at,
                   COALESCE(u.display_name, u.username) AS creator_name,
                   rr.department_id, d.name AS dept_name, rr.color, rr.review_activated
            FROM review_requests rr
            LEFT JOIN users u ON u.id = rr.created_by
            LEFT JOIN departments d ON d.id = rr.department_id
            ORDER BY rr.start_date ASC
        """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def update_review_request_color(request_id, color):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE review_requests SET color = %s WHERE id = %s", (color, request_id))
    conn.commit()
    cursor.close()
    conn.close()


def update_review_request_title(request_id, title):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE review_requests SET title = %s WHERE id = %s", (title, request_id))
    conn.commit()
    cursor.close()
    conn.close()


def get_all_review_requests_for_grid():
    """Return all review requests (active and inactive) with color for grid display."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT rr.id, rr.title, rr.start_date, rr.end_date, rr.department_id,
               rr.color, rr.active, rr.review_activated,
               COALESCE(u.display_name, u.username) AS creator_name
        FROM review_requests rr
        LEFT JOIN users u ON u.id = rr.created_by
        ORDER BY rr.created_at DESC
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def get_active_review_requests():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, start_date, end_date, department_id, color
        FROM review_requests
        WHERE active = TRUE
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def get_pending_review_requests_for_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT rr.id, rr.title, rr.start_date, rr.end_date, rr.color
        FROM review_requests rr
        WHERE rr.active = TRUE
          AND rr.department_id = (SELECT department_id FROM users WHERE id = %s)
          AND NOT EXISTS (
            SELECT 1 FROM review_responses resp
            WHERE resp.request_id = rr.id AND resp.user_id = %s
              AND resp.decided_at IS NOT NULL
          )
        ORDER BY rr.created_at DESC
    """, (user_id, user_id))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def mark_review_seen(request_id, user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO review_responses (request_id, user_id, seen_at)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE seen_at = COALESCE(seen_at, %s)
    """, (request_id, user_id, _now(), _now()))
    conn.commit()
    cursor.close()
    conn.close()


def mark_review_decided(request_id, user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO review_responses (request_id, user_id, seen_at, decided_at)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE decided_at = %s, seen_at = COALESCE(seen_at, %s)
    """, (request_id, user_id, _now(), _now(), _now(), _now()))
    conn.commit()
    cursor.close()
    conn.close()


def undo_review_decided(request_id, user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE review_responses SET decided_at = NULL WHERE request_id = %s AND user_id = %s",
        (request_id, user_id))
    conn.commit()
    cursor.close()
    conn.close()


def get_signed_off_reviews_for_user(user_id):
    """Return active review requests that this user has signed off on."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT rr.id, rr.title, rr.start_date, rr.end_date, rr.color, resp.decided_at
        FROM review_requests rr
        JOIN review_responses resp ON resp.request_id = rr.id AND resp.user_id = %s
        WHERE rr.active = TRUE AND resp.decided_at IS NOT NULL
          AND rr.department_id = (SELECT department_id FROM users WHERE id = %s)
        ORDER BY rr.start_date ASC
    """, (user_id, user_id))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def get_review_request_status(request_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT department_id FROM review_requests WHERE id = %s", (request_id,))
    rr = cursor.fetchone()
    dept_id = rr[0] if rr else None
    cursor.execute("""
        SELECT u.id, COALESCE(u.display_name, u.username) AS display_name,
               resp.seen_at, resp.decided_at
        FROM users u
        LEFT JOIN review_responses resp ON resp.user_id = u.id AND resp.request_id = %s
        WHERE u.active = TRUE AND u.department_id = %s
        ORDER BY COALESCE(u.display_name, u.username)
    """, (request_id, dept_id))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def get_review_signoff_user_ids():
    """Return a dict mapping review_request id -> set of user_ids who have signed off."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT resp.request_id, resp.user_id
        FROM review_responses resp
        JOIN review_requests rr ON rr.id = resp.request_id
        WHERE rr.active = TRUE AND resp.decided_at IS NOT NULL
    """)
    result = {}
    for req_id, uid in cursor.fetchall():
        result.setdefault(req_id, set()).add(uid)
    cursor.close()
    conn.close()
    return result


def toggle_review_request_active(request_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT active, review_activated FROM review_requests WHERE id = %s", (request_id,))
    row = cursor.fetchone()
    if row and not row[0] and not row[1]:
        cursor.execute(
            "UPDATE review_requests SET active = TRUE, review_activated = %s WHERE id = %s",
            (_now(), request_id))
    else:
        cursor.execute(
            "UPDATE review_requests SET active = NOT active WHERE id = %s",
            (request_id,))
    conn.commit()
    cursor.close()
    conn.close()


def delete_review_request(request_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM review_requests WHERE id = %s", (request_id,))
    conn.commit()
    cursor.close()
    conn.close()


# ---------------------------------------------------------------------------
# Departments
# ---------------------------------------------------------------------------

def get_all_departments():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, sort_order, is_fun FROM departments ORDER BY sort_order, name")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def create_department(name):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO departments (name) VALUES (%s)", (name,))
        conn.commit()
        return True, "Department created."
    except mysql.connector.IntegrityError:
        return False, "A department with that name already exists."
    finally:
        cursor.close()
        conn.close()


def delete_department(department_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET department_id = NULL WHERE department_id = %s", (department_id,))
    cursor.execute("DELETE FROM departments WHERE id = %s", (department_id,))
    conn.commit()
    cursor.close()
    conn.close()


def update_department_name(department_id, name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE departments SET name = %s WHERE id = %s", (name, department_id))
    conn.commit()
    cursor.close()
    conn.close()


def toggle_department_fun(department_id, is_fun):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE departments SET is_fun = %s WHERE id = %s", (1 if is_fun else 0, department_id))
    conn.commit()
    cursor.close()
    conn.close()


def set_user_department(user_id, department_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET department_id = %s WHERE id = %s",
                   (department_id if department_id else None, user_id))
    conn.commit()
    cursor.close()
    conn.close()


def get_user_department_id(user_id):
    """Return the department_id for a user, or None."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT department_id FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row[0] if row else None


def get_user_secondary_departments(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT department_id FROM user_secondary_departments WHERE user_id = %s", (user_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [r[0] for r in rows]


def set_user_secondary_departments(user_id, department_ids):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_secondary_departments WHERE user_id = %s", (user_id,))
    for dept_id in department_ids:
        cursor.execute("INSERT INTO user_secondary_departments (user_id, department_id) VALUES (%s, %s)",
                       (user_id, dept_id))
    conn.commit()
    cursor.close()
    conn.close()


def get_all_secondary_departments_map():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, department_id FROM user_secondary_departments ORDER BY user_id")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    result = {}
    for uid, dept_id in rows:
        result.setdefault(uid, []).append(dept_id)
    return result


def delete_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()


def reset_user_holidays(user_id):
    """Delete all vacation days for the user, withdraw all review sign-offs,
    and reset accrued_days_initial + start_date so they re-do the initial-setup flow on next login."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET accrued_days_initial = FALSE, start_date = NULL WHERE id = %s",
        (user_id,))
    cursor.execute("""
        DELETE vd FROM vacation_days vd
        JOIN team_members tm ON vd.member_id = tm.id
        JOIN users u ON u.username = tm.name
        WHERE u.id = %s
    """, (user_id,))
    cursor.execute(
        "UPDATE review_responses SET decided_at = NULL WHERE user_id = %s",
        (user_id,))
    conn.commit()
    cursor.close()
    conn.close()


def get_vacation_days_per_month(user_id, period_start, period_end):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT YEAR(vd.vacation_date) AS y, MONTH(vd.vacation_date) AS m, COUNT(*) AS cnt
        FROM vacation_days vd
        JOIN team_members tm ON vd.member_id = tm.id
        JOIN users u ON u.username = tm.name
        WHERE u.id = %s AND vd.status = 'approved'
          AND vd.self_paid = FALSE
          AND vd.vacation_date BETWEEN %s AND %s
        GROUP BY y, m
        ORDER BY y, m
    """, (user_id, period_start, period_end))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return {(int(y), int(m)): int(cnt) for y, m, cnt in rows}


def get_all_vacation_days_per_month(period_start, period_end):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, YEAR(vd.vacation_date) AS y, MONTH(vd.vacation_date) AS m, COUNT(*) AS cnt
        FROM vacation_days vd
        JOIN team_members tm ON vd.member_id = tm.id
        JOIN users u ON u.username = tm.name
        WHERE vd.status = 'approved'
          AND vd.self_paid = FALSE
          AND vd.vacation_date BETWEEN %s AND %s
        GROUP BY u.id, y, m
        ORDER BY u.id, y, m
    """, (period_start, period_end))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    result = {}
    for uid, y, m, cnt in rows:
        result.setdefault(int(uid), {})[(int(y), int(m))] = int(cnt)
    return result


def get_pre_admin_emails():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM pre_admins ORDER BY email")
    emails = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return emails


def set_pre_admin_emails(emails):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pre_admins")
    for email in emails:
        email = email.strip().lower()
        if email:
            cursor.execute("INSERT IGNORE INTO pre_admins (email) VALUES (%s)", (email,))
    conn.commit()
    cursor.close()
    conn.close()
