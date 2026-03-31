import mysql.connector
from mysql.connector import pooling
import hashlib
import secrets
from datetime import datetime, timedelta
import os

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'database': os.getenv('DB_NAME', 'vacation_db'),
    'user': os.getenv('DB_USER', 'vacation_user'),
    'password': os.getenv('DB_PASSWORD', 'vacation_pass')
}

_pool = pooling.MySQLConnectionPool(pool_name="app", pool_size=5, **DB_CONFIG)


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
        "SELECT id, username, must_change_password, theme, role, initials, font FROM users WHERE username = %s AND password_hash = %s",
        (username, hash_password(password))
    )
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return user


def register_user(username, password, display_name=None, email=None, font=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM users")
        is_first = cursor.fetchone()[0] == 0
        role = 'admin' if is_first else 'user'
        cursor.execute(
            "INSERT INTO users (username, password_hash, must_change_password, initials, display_name, email, font, role) VALUES (%s, %s, FALSE, %s, %s, %s, %s, %s)",
            (username, hash_password(password), username, display_name, email, font, role)
        )
        conn.commit()
        return True, "Account created! You can now log in."
    except mysql.connector.IntegrityError:
        return False, "Shortname already exists."
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
        "SELECT id, username, must_change_password, theme, role, initials, font FROM users WHERE session_token = %s",
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
    cursor.execute("SELECT id, username, display_name, email, role, days_off_per_year, accrued_days, start_date FROM users ORDER BY username")
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


def _prorate_entitlement(days_off_per_year, start_date, period_start, period_end):
    """If start_date is within the period, prorate. Otherwise full entitlement."""
    base = float(days_off_per_year)
    if start_date and period_start <= start_date <= period_end:
        months_in_period = (period_end.year - start_date.year) * 12 + period_end.month - start_date.month + 1
        if months_in_period < 1:
            months_in_period = 1
        return round(base / 12 * months_in_period, 1)
    return base


def get_vacation_summary(user_id, period_start, period_end):
    from datetime import date as _date
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT days_off_per_year, start_date FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    base_days = row[0] if row and row[0] is not None else 34
    user_start = row[1] if row else None
    entitlement = _prorate_entitlement(base_days, user_start, period_start, period_end)

    cursor.execute("""
        SELECT COUNT(*) FROM vacation_days vd
        JOIN team_members tm ON vd.member_id = tm.id
        JOIN users u ON u.username = tm.name
        WHERE u.id = %s AND vd.status = 'approved'
          AND vd.vacation_date BETWEEN %s AND %s
    """, (user_id, period_start, period_end))
    used = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM vacation_days vd
        JOIN team_members tm ON vd.member_id = tm.id
        JOIN users u ON u.username = tm.name
        WHERE u.id = %s AND vd.status = 'pending'
          AND vd.vacation_date BETWEEN %s AND %s
    """, (user_id, period_start, period_end))
    pending = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    # Calculate accrued dynamically: (entitlement / 12) * months elapsed
    today = _date.today()
    accrual_start = max(period_start, user_start) if user_start and user_start > period_start else period_start
    months_elapsed = (today.year - accrual_start.year) * 12 + today.month - accrual_start.month
    if months_elapsed < 0:
        months_elapsed = 0
    accrued = round(float(base_days) / 12 * months_elapsed, 1)

    return {
        'days_off_per_year': entitlement,
        'used': used,
        'pending': pending,
        'remaining': entitlement - used,
        'accrued': accrued,
        'accrual_start': accrual_start,
        'months_elapsed': months_elapsed,
        'base_days': float(base_days),
    }


def get_period_vacation_summary(user_id, period_start, period_end):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT days_off_per_year, start_date FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    base_days = row[0] if row and row[0] is not None else 34
    user_start = row[1] if row else None
    entitlement = _prorate_entitlement(base_days, user_start, period_start, period_end)

    cursor.execute("""
        SELECT COUNT(*) FROM vacation_days vd
        JOIN team_members tm ON vd.member_id = tm.id
        JOIN users u ON u.username = tm.name
        WHERE u.id = %s AND vd.status = 'approved'
          AND vd.vacation_date BETWEEN %s AND %s
    """, (user_id, period_start, period_end))
    used = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM vacation_days vd
        JOIN team_members tm ON vd.member_id = tm.id
        JOIN users u ON u.username = tm.name
        WHERE u.id = %s AND vd.status = 'pending'
          AND vd.vacation_date BETWEEN %s AND %s
    """, (user_id, period_start, period_end))
    pending = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    return {
        'days_off_per_year': entitlement,
        'used': used,
        'pending': pending,
        'remaining': entitlement - used,
    }


def get_all_users_period_summary(period_start, period_end):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, COALESCE(u.display_name, u.username) AS display_name,
               u.days_off_per_year, u.start_date,
               COALESCE(SUM(CASE WHEN vd.status = 'approved' THEN 1 ELSE 0 END), 0) AS used,
               COALESCE(SUM(CASE WHEN vd.status = 'pending' THEN 1 ELSE 0 END), 0) AS pending
        FROM users u
        LEFT JOIN team_members tm ON tm.name = u.username
        LEFT JOIN vacation_days vd ON tm.id = vd.member_id
            AND vd.vacation_date BETWEEN %s AND %s
        GROUP BY u.id, u.display_name, u.username, u.days_off_per_year, u.start_date
        ORDER BY COALESCE(u.display_name, u.username)
    """, (period_start, period_end))
    raw = cursor.fetchall()
    cursor.close()
    conn.close()
    # Prorate entitlement per user
    results = []
    for uid, display_name, base_days, user_start, used, pending in raw:
        base = base_days if base_days is not None else 34
        entitlement = _prorate_entitlement(base, user_start, period_start, period_end)
        results.append((uid, display_name, entitlement, int(used), int(pending)))
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
                    (member_id, current, user_id, user_id, datetime.now()))
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

def add_vacation_for_user(user_id, start_date, end_date, is_admin=False, requested_by=None):
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
    if is_admin:
        status = 'approved'
    else:
        status = 'pending'
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
                   (member_id, vacation_date, status, requested_by, approved_by, approved_at)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (member_id, current, status, requested_by,
                 requested_by if is_admin else None,
                 datetime.now() if is_admin else None)
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


def get_pending_requests():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT vd.id, COALESCE(u.display_name, u.username) as display,
               vd.vacation_date, vd.status, vd.requested_by, vd.created_at
        FROM vacation_days vd
        JOIN team_members tm ON vd.member_id = tm.id
        LEFT JOIN users u ON u.username = tm.name
        WHERE vd.status IN ('pending', 'pending_removal')
        ORDER BY vd.created_at, vd.vacation_date
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def get_pending_requests_grouped():
    """Group pending requests by user+status+created_at (same form submission)."""
    rows = get_pending_requests()
    groups = []
    current = None
    for vid, display, vdate, status, req_by, created_at in rows:
        if (current and current['display'] == display
                and current['status'] == status
                and current['created_at'] == created_at):
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
                'display': display,
                'start_date': vdate,
                'end_date': vdate,
                'status': status,
                'req_by': req_by,
                'created_at': created_at,
                'count': 1,
            }
    if current:
        groups.append(current)
    return groups


def approve_vacation_bulk(vacation_day_ids, approved_by_username):
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now()
    for vid in vacation_day_ids:
        cursor.execute("SELECT status FROM vacation_days WHERE id = %s", (vid,))
        row = cursor.fetchone()
        if not row:
            continue
        if row[0] == 'pending':
            cursor.execute(
                "UPDATE vacation_days SET status = 'approved', approved_by = %s, approved_at = %s WHERE id = %s",
                (approved_by_username, now, vid))
        elif row[0] == 'pending_removal':
            cursor.execute("DELETE FROM vacation_days WHERE id = %s", (vid,))
    conn.commit()
    cursor.close()
    conn.close()


def reject_vacation_bulk(vacation_day_ids):
    conn = get_db_connection()
    cursor = conn.cursor()
    for vid in vacation_day_ids:
        cursor.execute("SELECT status FROM vacation_days WHERE id = %s", (vid,))
        row = cursor.fetchone()
        if not row:
            continue
        if row[0] == 'pending':
            cursor.execute("DELETE FROM vacation_days WHERE id = %s", (vid,))
        elif row[0] == 'pending_removal':
            cursor.execute("UPDATE vacation_days SET status = 'approved' WHERE id = %s", (vid,))
    conn.commit()
    cursor.close()
    conn.close()


def get_pending_count():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM vacation_days WHERE status IN ('pending', 'pending_removal')")
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return count


def approve_vacation(vacation_day_id, approved_by_username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM vacation_days WHERE id = %s", (vacation_day_id,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        conn.close()
        return False
    status = row[0]
    if status == 'pending':
        cursor.execute(
            "UPDATE vacation_days SET status = 'approved', approved_by = %s, approved_at = %s WHERE id = %s",
            (approved_by_username, datetime.now(), vacation_day_id)
        )
    elif status == 'pending_removal':
        cursor.execute("DELETE FROM vacation_days WHERE id = %s", (vacation_day_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return True


def reject_vacation(vacation_day_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM vacation_days WHERE id = %s", (vacation_day_id,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        conn.close()
        return False
    status = row[0]
    if status == 'pending':
        cursor.execute("DELETE FROM vacation_days WHERE id = %s", (vacation_day_id,))
    elif status == 'pending_removal':
        cursor.execute(
            "UPDATE vacation_days SET status = 'approved' WHERE id = %s",
            (vacation_day_id,)
        )
    conn.commit()
    cursor.close()
    conn.close()
    return True


def request_vacation_removal(vacation_day_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM vacation_days WHERE id = %s", (vacation_day_id,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        conn.close()
        return False, "Vacation day not found."
    if row[0] == 'pending_removal':
        cursor.close()
        conn.close()
        return False, "Removal already requested."
    if row[0] != 'approved':
        cursor.close()
        conn.close()
        return False, "Can only request removal of approved vacation."
    cursor.execute(
        "UPDATE vacation_days SET status = 'pending_removal' WHERE id = %s",
        (vacation_day_id,)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return True, "Removal requested."


def cancel_pending_request(vacation_day_id, username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM vacation_days WHERE id = %s AND status = 'pending' AND requested_by = %s",
        (vacation_day_id, username)
    )
    deleted = cursor.rowcount > 0
    conn.commit()
    cursor.close()
    conn.close()
    return deleted


def get_user_vacations(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT vd.id, vd.vacation_date, vd.status, vd.requested_by, vd.approved_by
        FROM vacation_days vd
        JOIN team_members tm ON vd.member_id = tm.id
        JOIN users u ON u.username = tm.name
        WHERE u.id = %s
        ORDER BY vd.vacation_date
    """, (user_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def get_user_vacations_grouped(user_id):
    """Group a user's vacations into periods by status + created_at."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT vd.id, vd.vacation_date, vd.status, vd.requested_by,
               vd.approved_by, vd.created_at
        FROM vacation_days vd
        JOIN team_members tm ON vd.member_id = tm.id
        JOIN users u ON u.username = tm.name
        WHERE u.id = %s
        ORDER BY vd.status, vd.created_at, vd.vacation_date
    """, (user_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    groups = []
    current = None
    for vid, vdate, status, req_by, approved_by, created_at in rows:
        if (current and current['status'] == status
                and current['created_at'] == created_at):
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
                'status': status,
                'start_date': vdate,
                'end_date': vdate,
                'req_by': req_by,
                'approved_by': approved_by,
                'created_at': created_at,
                'count': 1,
            }
    if current:
        groups.append(current)

    # Sort by start_date so periods appear chronologically
    groups.sort(key=lambda g: g['start_date'])
    return groups


def request_vacation_removal_bulk(ids):
    """Mark multiple approved vacation days as pending_removal."""
    conn = get_db_connection()
    cursor = conn.cursor()
    fmt = ','.join(['%s'] * len(ids))
    cursor.execute(
        f"UPDATE vacation_days SET status = 'pending_removal' "
        f"WHERE id IN ({fmt}) AND status = 'approved'",
        tuple(ids)
    )
    updated = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    return updated


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


def cancel_pending_request_bulk(ids, username):
    """Cancel multiple pending vacation requests."""
    conn = get_db_connection()
    cursor = conn.cursor()
    fmt = ','.join(['%s'] * len(ids))
    cursor.execute(
        f"DELETE FROM vacation_days WHERE id IN ({fmt}) "
        f"AND status = 'pending' AND requested_by = %s",
        tuple(ids) + (username,)
    )
    deleted = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    return deleted


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


def get_all_users_for_calendar():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, display_name, initials, font FROM users ORDER BY username")
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return users


def get_vacations_for_date_range(start_date, end_date):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, COALESCE(u.display_name, u.username) as display,
               vd.vacation_date, vd.status
        FROM users u
        LEFT JOIN team_members tm ON tm.name = u.username
        LEFT JOIN vacation_days vd ON tm.id = vd.member_id
            AND vd.vacation_date BETWEEN %s AND %s
        ORDER BY COALESCE(u.display_name, u.username), vd.vacation_date
    """, (start_date, end_date))
    vacations = cursor.fetchall()
    cursor.close()
    conn.close()
    return vacations


def get_all_enabled_holidays():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT holiday_date FROM period_holidays WHERE enabled = TRUE")
    holidays = {row[0] for row in cursor.fetchall()}
    cursor.close()
    conn.close()
    return holidays


def get_holidays_for_date_range(start_date, end_date):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT holiday_date, name, id FROM period_holidays
        WHERE enabled = TRUE AND holiday_date BETWEEN %s AND %s
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
    cursor.execute("SELECT id, label, start_date, end_date FROM holiday_periods ORDER BY start_date")
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


def get_period_holidays(period_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, holiday_date, enabled FROM period_holidays
        WHERE period_id = %s ORDER BY holiday_date
    """, (period_id,))
    holidays = cursor.fetchall()
    cursor.close()
    conn.close()
    return holidays


def toggle_period_holiday(holiday_id):
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


def update_period_holiday_date(holiday_id, new_date):
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
        "INSERT INTO period_holidays (period_id, name, holiday_date, enabled) VALUES (%s, %s, %s, TRUE)",
        (period_id, name, holiday_date))
    conn.commit()
    cursor.close()
    conn.close()


def delete_period_holiday(holiday_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT period_id FROM period_holidays WHERE id = %s", (holiday_id,))
    row = cursor.fetchone()
    period_id = row[0] if row else None
    if period_id:
        cursor.execute("DELETE FROM period_holidays WHERE id = %s", (holiday_id,))
        conn.commit()
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
