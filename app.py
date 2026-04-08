import os
import secrets
from datetime import datetime, date, timedelta
from functools import wraps
from io import BytesIO

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, make_response
)
from openpyxl import Workbook

import db
from migrate import run_migrations

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.config['TEMPLATES_AUTO_RELOAD'] = True

run_migrations()


# ---------------------------------------------------------------------------
# Template filters
# ---------------------------------------------------------------------------

@app.template_filter('fmtdate')
def format_date(value):
    """Format a date as '1. feb - 2026'."""
    if not value:
        return ''
    return f"{value.day}. {value.strftime('%b').lower()} - {value.year}"


@app.template_filter('fmtdatetime')
def format_datetime(value):
    """Format a datetime as '1. feb - 2026 14:30'."""
    if not value:
        return ''
    return f"{value.day}. {value.strftime('%b').lower()} - {value.year} {value.strftime('%H:%M')}"


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(500)
def internal_error(e):
    import traceback
    tb = traceback.format_exception(type(e), e, e.__traceback__)
    return render_template('error.html', error=''.join(tb)), 500


@app.errorhandler(Exception)
def handle_exception(e):
    if app.debug:
        raise e
    import traceback
    tb = traceback.format_exception(type(e), e, e.__traceback__)
    return render_template('error.html', error=''.join(tb)), 500


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_htmx():
    return request.headers.get('HX-Request') == 'true'


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            token = request.cookies.get('session_token')
            if token:
                user = db.get_user_by_session_token(token)
                if user:
                    session['user_id'] = user[0]
                    session['username'] = user[1]
                    session['must_change_password'] = bool(user[2])
                    session['theme'] = user[3] or 'light'
                    session['role'] = user[4] or 'user'
                    session['initials'] = user[5] or user[1]
                    session['font'] = user[6] or ''
                    session['email'] = user[7] or ''
                    session['needs_initial_accrued'] = db.needs_initial_accrued(user[0])
                    session['department_id'] = db.get_user_department_id(user[0])
                else:
                    return redirect(url_for('login'))
            else:
                return redirect(url_for('login'))
        if session.get('must_change_password'):
            return redirect(url_for('force_password'))
        if session.get('needs_initial_accrued'):
            return redirect(url_for('initial_accrued'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Permission denied.', 'error')
            return redirect(url_for('calendar_redirect'))
        return f(*args, **kwargs)
    return decorated


@app.context_processor
def inject_globals():
    is_admin = session.get('role') == 'admin'
    all_departments = db.get_all_departments() if session.get('user_id') else []
    user_dept_id = db.get_user_department_id(session['user_id']) if session.get('user_id') else None
    session['department_id'] = user_dept_id
    current_dept_id = session.get('viewing_department_id') or user_dept_id
    current_dept_name = None
    is_fun_dept = False
    for did, dname, _, dfun in all_departments:
        if did == current_dept_id:
            current_dept_name = dname
        if did == user_dept_id:
            is_fun_dept = bool(dfun)
    user_email = session.get('email')
    if not user_email and session.get('user_id'):
        profile = db.get_user_profile(session['user_id'])
        if profile:
            user_email = profile[1] or ''
            session['email'] = user_email
    user_email = user_email or ''
    return {
        'theme': session.get('theme', 'light'),
        'user_id': session.get('user_id'),
        'username': session.get('username', ''),
        'initials': session.get('initials', session.get('username', '')),
        'user_font': session.get('font', ''),
        'is_admin': is_admin,
        'is_superuser': user_email == 'zeth.odderskov@borsen.dk',
        'active_tab': request.endpoint or '',
        'nav_departments': all_departments,
        'nav_current_dept_id': current_dept_id,
        'nav_current_dept_name': current_dept_name,
        'is_fun_dept': is_fun_dept,
        'show_toggles': is_fun_dept,
        'viewing_own_dept': current_dept_id == user_dept_id,
    }


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not username or not password:
            flash('Please fill in all fields.', 'error')
            return redirect(url_for('login'))
        user = db.authenticate_user(username, password)
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['must_change_password'] = bool(user[2])
            session['theme'] = user[3] or 'light'
            session['role'] = user[4] or 'user'
            session['initials'] = user[5] or user[1]
            session['font'] = user[6] or ''
            session['email'] = user[7] or ''
            session['needs_initial_accrued'] = db.needs_initial_accrued(user[0])
            session['department_id'] = db.get_user_department_id(user[0])
            token = db.create_session_token(user[0])
            resp = redirect(url_for('calendar_redirect'))
            resp.set_cookie('session_token', token, max_age=2592000, httponly=True, samesite='Lax')
            return resp
        flash('Invalid username or password.', 'error')
        return redirect(url_for('login'))
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        shortname = request.form.get('shortname', '').strip()
        display_name = request.form.get('display_name', '').strip()
        email = request.form.get('email', '').strip() or None
        font = request.form.get('font', '').strip() or None
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')
        department_id = request.form.get('department_id', type=int) or None
        if not shortname or not display_name or not password or not confirm:
            flash('Please fill in all fields.', 'error')
            return redirect(url_for('register'))
        if password != confirm:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('register'))
        if len(password) < 4:
            flash('Password must be at least 4 characters.', 'error')
            return redirect(url_for('register'))
        success, msg = db.register_user(shortname, password, display_name=display_name, email=email, font=font, department_id=department_id)
        if success:
            flash(msg, 'success')
            return redirect(url_for('login'))
        flash(msg, 'error')
        return redirect(url_for('register'))
    departments = db.get_all_departments()
    return render_template('register.html', departments=departments)


@app.route('/logout', methods=['POST'])
def logout():
    user_id = session.get('user_id')
    if user_id:
        db.clear_session_token(user_id)
    session.clear()
    resp = redirect(url_for('login'))
    resp.delete_cookie('session_token')
    return resp


@app.route('/force-password', methods=['GET', 'POST'])
def force_password():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        new_pw = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')
        if not new_pw:
            flash('Password cannot be empty.', 'error')
        elif new_pw != confirm:
            flash('Passwords do not match.', 'error')
        elif len(new_pw) < 4:
            flash('Password must be at least 4 characters.', 'error')
        else:
            db.update_password(session['user_id'], new_pw)
            session['must_change_password'] = False
            flash('Password updated!', 'success')
            return redirect(url_for('calendar_redirect'))
        return redirect(url_for('force_password'))
    return render_template('force_password.html')


@app.route('/initial-accrued', methods=['GET', 'POST'])
def initial_accrued():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Look up current period
    period_id = db.get_current_period_id()
    period_start = None
    period_end = None
    period_label = None
    days_off = 34
    if period_id:
        for pid, plabel, pstart, pend in db.get_holiday_periods():
            if pid == period_id:
                period_start = pstart
                period_end = pend
                period_label = plabel
                days_off = db.get_vacation_summary(
                    session['user_id'], pstart, pend)['days_off_per_year']
                break

    if request.method == 'POST':
        raw_used = request.form.get('days_used', '').strip()
        started_this_period = request.form.get('started_this_period') == 'yes'
        start_date_str = request.form.get('start_date', '').strip()
        try:
            days_used = int(raw_used) if raw_used else 0
            if days_used < 0:
                raise ValueError
        except (ValueError, TypeError):
            flash('Please enter a valid number (0 or more).', 'error')
            return redirect(url_for('initial_accrued'))
        user_start = None
        if started_this_period and start_date_str:
            user_start = date.fromisoformat(start_date_str)
        db.set_initial_accrued(session['user_id'], days_used, period_start,
                               start_date=user_start)
        session['needs_initial_accrued'] = False
        flash('Holiday balance saved!', 'success')
        return redirect(url_for('calendar_redirect'))
    return render_template('initial_accrued.html',
                           period_label=period_label, days_off=days_off,
                           period_start=period_start, period_end=period_end)


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

@app.route('/')
@login_required
def home():
    return redirect(url_for('calendar_redirect'))


@app.route('/calendar')
@login_required
def calendar_redirect():
    dept_id = session.get('viewing_department_id') or session.get('department_id')
    if not dept_id:
        departments = db.get_all_departments()
        if departments:
            dept_id = departments[0][0]
        else:
            flash('No departments have been created yet.', 'warning')
            return redirect(url_for('settings') if session.get('role') == 'admin' else url_for('profile'))
    return redirect(url_for('calendar_view', dept_id=dept_id))


@app.route('/calendar/<int:dept_id>')
@login_required
def calendar_view(dept_id):
    # Verify department exists
    all_departments = db.get_all_departments()
    dept_exists = any(d[0] == dept_id for d in all_departments)
    if not dept_exists:
        flash('Department not found.', 'error')
        return redirect(url_for('calendar_redirect'))

    # Admins can view any department; non-admins can only view their own
    user_dept_id = db.get_user_department_id(session['user_id'])
    if session.get('role') != 'admin' and user_dept_id != dept_id:
        if user_dept_id is None:
            flash('You are not assigned to any department.', 'warning')
            return redirect(url_for('profile'))
        return redirect(url_for('calendar_view', dept_id=user_dept_id))

    # Track which department the admin is currently viewing
    session['viewing_department_id'] = dept_id

    today = date.today()

    start_str = request.args.get('from')
    end_str = request.args.get('to')
    start_date = date.fromisoformat(start_str) if start_str else today
    end_date = date.fromisoformat(end_str) if end_str else today + timedelta(days=29)

    users = db.get_all_users_for_calendar(department_id=dept_id)

    # Group users by department for the template (single department now)
    dept_groups = []
    if users:
        dept_name = users[0][6] or 'Unassigned'
        dept_groups.append({'id': dept_id, 'name': dept_name, 'users': list(users)})

    vacations_data = db.get_vacations_for_date_range(start_date, end_date)
    holidays_data = db.get_holidays_for_date_range(start_date, end_date)

    days = []
    current = start_date
    while current <= end_date:
        days.append(current)
        current += timedelta(days=1)

    holiday_dict = {}
    for hdate, hname, hid in holidays_data:
        holiday_dict[hdate] = hname

    vacation_dict = {}
    for uid, display, vdate, status in vacations_data:
        if not vdate:
            continue
        vacation_dict.setdefault(display, set()).add(vdate)

    weekend_days = set()
    for d in days:
        if d.weekday() in (5, 6):
            weekend_days.add(d)

    total_vacations = db.get_vacation_count()

    # Holiday period summary (only show on user's own department)
    viewing_own_dept = (dept_id == user_dept_id)
    period_id = db.get_current_period_id()
    period_summary = None
    period_label = None
    period_start = None
    period_end_date = None
    admin_summaries = []
    if period_id:
        periods = db.get_holiday_periods()
        for pid, plabel, pstart, pend in periods:
            if pid == period_id:
                period_label = plabel
                period_start = pstart
                period_end_date = pend
                period_summary = db.get_period_vacation_summary(
                    session['user_id'], pstart, pend)
                months_left = (pend.year - today.year) * 12 + pend.month - today.month
                if months_left < 1:
                    months_left = 1
                period_summary['avg_per_month'] = round(
                    period_summary['remaining'] / months_left, 1)
                period_summary['months_left'] = months_left
                if session.get('role') == 'admin':
                    admin_summaries = db.get_all_users_period_summary(pstart, pend, department_id=dept_id)
                break

    if period_start and period_end_date:
        vacation_summary = db.get_vacation_summary(
            session['user_id'], period_start, period_end_date)
    else:
        vacation_summary = {'days_off_per_year': 34, 'used': 0,
                            'remaining': 34, 'accrued': 0}

    # Build monthly bar chart data for the period
    monthly_chart = []
    if period_start and period_end_date and period_summary:
        usage_by_month = db.get_vacation_days_per_month(
            session['user_id'], period_start, period_end_date)
        suggested = round(period_summary['remaining'] / period_summary['months_left'], 1)
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        d = date(period_start.year, period_start.month, 1)
        end_m = date(period_end_date.year, period_end_date.month, 1)
        while d <= end_m:
            used_m = usage_by_month.get((d.year, d.month), 0)
            is_past = (d.year < today.year) or (d.year == today.year and d.month < today.month)
            is_current = (d.year == today.year and d.month == today.month)
            monthly_chart.append({
                'label': month_names[d.month - 1],
                'year': d.year,
                'used': used_m,
                'is_past': is_past,
                'is_current': is_current,
                'is_future': not is_past and not is_current,
            })
            if d.month == 12:
                d = date(d.year + 1, 1, 1)
            else:
                d = date(d.year, d.month + 1, 1)


    # Review period requests (banner only on user's own department)
    pending_reviews = db.get_pending_review_requests_for_user(session['user_id']) if viewing_own_dept else []
    all_grid_reviews = db.get_all_review_requests_for_grid()
    signoff_map = db.get_review_signoff_user_ids()  # {request_id: {user_ids}}
    all_holidays = db.get_all_enabled_holidays() if pending_reviews else set()

    # Build per-user review cell info: user_review_cells[uid][date] = (color, opacity, signed)
    # Priority: active+pending > active+signed > inactive (higher priority wins)
    PRIORITY_ACTIVE_PENDING = 3
    PRIORITY_ACTIVE_SIGNED = 2
    PRIORITY_INACTIVE = 1
    user_review_cells = {}  # uid -> {date -> (color, opacity, signed)}
    user_review_priority = {}  # uid -> {date -> priority}
    pending_review_ids = {rr[0] for rr in pending_reviews}
    review_dates = set()

    for rr in all_grid_reviews:
        # (id, title, start_date, end_date, department_id, color, active)
        req_id, _, rr_start, rr_end, rr_dept_id, rr_color, rr_active = rr
        signed_users = signoff_map.get(req_id, set())
        d = rr_start
        while d <= rr_end:
            if rr_active:
                review_dates.add(d)
            for u in users:
                uid = u[0]
                u_dept = u[5]
                if rr_dept_id and u_dept != rr_dept_id:
                    continue
                if rr_active:
                    if uid in signed_users:
                        prio = PRIORITY_ACTIVE_SIGNED
                        cell = (rr_color, 0.45, True)
                    else:
                        prio = PRIORITY_ACTIVE_PENDING
                        cell = (rr_color, 1.0, False)
                else:
                    prio = PRIORITY_INACTIVE
                    cell = (rr_color, 0.15, False)
                cur_prio = user_review_priority.get(uid, {}).get(d, 0)
                if prio > cur_prio:
                    user_review_cells.setdefault(uid, {})[d] = cell
                    user_review_priority.setdefault(uid, {})[d] = prio
            d += timedelta(days=1)

    cal_base = url_for('calendar_view', dept_id=dept_id)

    template_data = {
        'today': today,
        'start_date': start_date,
        'end_date': end_date,
        'days': days,
        'users': users,
        'dept_groups': dept_groups,
        'cal_base': cal_base,
        'cal_dept_id': dept_id,
        'holiday_dict': holiday_dict,
        'vacation_dict': vacation_dict,
        'weekend_days': weekend_days,
        'total_vacations': total_vacations,
        'vacation_summary': vacation_summary,
        'current_year': today.year,
        'period_summary': period_summary if viewing_own_dept else None,
        'period_label': period_label,
        'period_end_date': period_end_date,
        'monthly_chart': monthly_chart,
        'suggested_per_month': suggested if monthly_chart else 0,
        'admin_summaries': admin_summaries,
        'pending_reviews': pending_reviews,
        'holidays': all_holidays,
        'review_dates': review_dates,
        'user_review_cells': user_review_cells,
        'presets': [
            {'label': '7 days',  'from': today.isoformat(), 'to': (today + timedelta(days=6)).isoformat(),  'active': start_date == today and (end_date - start_date).days == 6},
            {'label': '14 days', 'from': today.isoformat(), 'to': (today + timedelta(days=13)).isoformat(), 'active': start_date == today and (end_date - start_date).days == 13},
            {'label': '30 days', 'from': today.isoformat(), 'to': (today + timedelta(days=29)).isoformat(), 'active': start_date == today and (end_date - start_date).days == 29},
            {'label': '60 days', 'from': today.isoformat(), 'to': (today + timedelta(days=59)).isoformat(), 'active': start_date == today and (end_date - start_date).days == 59},
            {'label': '90 days', 'from': today.isoformat(), 'to': (today + timedelta(days=89)).isoformat(), 'active': start_date == today and (end_date - start_date).days == 89},
        ] + ([{
            'label': 'Entire year',
            'from': period_start.isoformat(),
            'to': period_end_date.isoformat(),
            'active': period_start == start_date and period_end_date == end_date,
        }] if period_start and period_end_date else []),
        'active_tab': 'calendar_view',
    }

    if is_htmx():
        return render_template('partials/_calendar_grid.html', **template_data)
    return render_template('calendar.html', **template_data)


@app.route('/vacations', methods=['POST'])
@login_required
def add_vacation():
    user_id = request.form.get('user_id', type=int)
    vacation_date = request.form.get('vacation_date')
    end_date = request.form.get('end_date')
    if not user_id or not vacation_date:
        flash('Please select a user and date.', 'error')
        return redirect(url_for('calendar_redirect'))
    start = date.fromisoformat(vacation_date)
    end = date.fromisoformat(end_date) if end_date else start
    if start > end:
        flash('End date must be after start date.', 'error')
        return redirect(url_for('calendar_redirect'))
    requester = session.get('username', '')
    added, skipped = db.add_vacation_for_user(user_id, start, end, requested_by=requester)
    if added:
        flash(f'Added {added} vacation day(s)!', 'success')
    if skipped:
        flash(f'Skipped {skipped} duplicate day(s).', 'info')
    referer = request.form.get('redirect') or url_for('calendar_redirect')
    return redirect(referer)


@app.route('/vacations/<int:vacation_id>', methods=['DELETE'])
@login_required
def delete_vacation(vacation_id):
    db.delete_vacation(vacation_id)
    flash('Vacation day deleted.', 'success')
    return redirect(url_for('calendar_redirect'))


@app.route('/vacations/remove-by-dates', methods=['POST'])
@login_required
def remove_vacations_by_dates():
    user_id = request.form.get('user_id', type=int)
    start = request.form.get('start_date')
    end = request.form.get('end_date')
    if not user_id or not start or not end:
        flash('Missing parameters.', 'error')
        return redirect(url_for('calendar_redirect'))
    # Non-admins can only remove their own vacations
    if session.get('role') != 'admin' and user_id != session.get('user_id'):
        flash('You can only remove your own vacations.', 'error')
        return redirect(url_for('calendar_redirect'))
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    ids = db.get_vacation_ids_for_user_dates(user_id, start_date, end_date)
    if ids:
        deleted = db.delete_vacation_bulk(ids)
        flash(f'Deleted {deleted} vacation day(s).', 'success')
    else:
        flash('No vacation days found in that range.', 'warning')
    return redirect(url_for('calendar_redirect'))


@app.route('/vacations/export')
@login_required
def export_vacations():
    all_vacations = db.get_all_vacations()
    wb = Workbook()
    ws = wb.active
    ws.title = "Vacations"
    ws.append(["Team Member", "Vacation Date"])
    for name, vdate, vid, status in all_vacations:
        ws.append([name, format_date(vdate)])
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    resp = make_response(output.read())
    resp.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    resp.headers['Content-Disposition'] = f'attachment; filename=team_vacations_{datetime.now().strftime("%Y%m%d")}.xlsx'
    return resp


# ---------------------------------------------------------------------------
# My Vacations
# ---------------------------------------------------------------------------

@app.route('/my-vacations')
@login_required
def my_vacations():
    groups = db.get_user_vacations_grouped(session['user_id'])
    holidays = db.get_all_enabled_holidays()
    signed_reviews = db.get_signed_off_reviews_for_user(session['user_id'])
    return render_template('my_vacations.html', groups=groups,
                           holidays=holidays, signed_reviews=signed_reviews,
                           active_tab='my_vacations')


@app.route('/vacations/<int:vacation_day_id>/request-removal', methods=['POST'])
@login_required
def request_removal(vacation_day_id):
    db.delete_vacation(vacation_day_id)
    flash('Vacation day deleted.', 'success')
    return redirect(url_for('my_vacations'))


@app.route('/vacations/bulk-removal', methods=['POST'])
@login_required
def bulk_request_removal():
    ids = request.form.getlist('ids', type=int)
    if not ids:
        flash('No vacation days selected.', 'warning')
        return redirect(url_for('my_vacations'))
    deleted = db.delete_vacation_bulk(ids)
    flash(f'{deleted} vacation day(s) deleted.', 'success')
    return redirect(url_for('my_vacations'))


# ---------------------------------------------------------------------------
# Holidays
# ---------------------------------------------------------------------------

@app.route('/holidays', methods=['GET'])
@login_required
def holidays():
    all_holidays = db.get_all_holidays()
    return render_template('holidays.html', holidays=all_holidays, active_tab='holidays')


@app.route('/holidays', methods=['POST'])
@login_required
def add_holiday():
    name = request.form.get('holiday_name', '').strip()
    holiday_date = request.form.get('holiday_date')
    end_date = request.form.get('end_date')
    if not name:
        flash('Please enter a holiday name.', 'error')
        return redirect(url_for('holidays'))
    if not holiday_date:
        flash('Please select a date.', 'error')
        return redirect(url_for('holidays'))
    start = date.fromisoformat(holiday_date)
    if end_date:
        end = date.fromisoformat(end_date)
        if start > end:
            flash('End date must be after start date.', 'error')
            return redirect(url_for('holidays'))
        added, skipped = db.add_holiday_range(start, end, name)
        if added:
            flash(f'Added {added} holiday day(s)!', 'success')
        if skipped:
            flash(f'Skipped {skipped} duplicate day(s).', 'info')
    else:
        success, msg = db.add_holiday(start, name)
        flash(msg, 'success' if success else 'warning')
    return redirect(url_for('holidays'))


@app.route('/holidays/<int:holiday_id>', methods=['DELETE'])
@login_required
def delete_holiday(holiday_id):
    db.delete_holiday(holiday_id)
    all_holidays = db.get_all_holidays()
    return render_template('partials/_holiday_list.html', holidays=all_holidays)


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@app.route('/events')
@login_required
def events():
    all_events = db.get_all_events()
    events_with_responses = []
    for eid, ename, created_at in all_events:
        responses = db.get_event_responses(eid)
        events_with_responses.append((eid, ename, created_at, responses))
    return render_template('events.html', events=events_with_responses, active_tab='events')


@app.route('/events', methods=['POST'])
@login_required
def create_event():
    name = request.form.get('event_name', '').strip()
    if not name:
        flash('Please enter an event name.', 'error')
        return redirect(url_for('events'))
    success, msg = db.create_event(name)
    flash(msg, 'success' if success else 'error')
    return redirect(url_for('events'))


@app.route('/events/<int:event_id>', methods=['DELETE'])
@login_required
def delete_event(event_id):
    db.delete_event(event_id)
    if is_htmx():
        all_events = db.get_all_events()
        events_with_responses = []
        for eid, ename, created_at in all_events:
            responses = db.get_event_responses(eid)
            events_with_responses.append((eid, ename, created_at, responses))
        return render_template('events.html', events=events_with_responses, active_tab='events')
    return redirect(url_for('events'))


@app.route('/events/<int:event_id>')
@login_required
def event_detail(event_id):
    event = db.get_event_by_id(event_id)
    if not event:
        flash('Event not found.', 'error')
        return redirect(url_for('events'))
    eid, ename, created_at = event
    responses = db.get_event_responses(eid)
    going = [r for r in responses if r[3] is True or r[3] == 1]
    not_going = [r for r in responses if r[3] is not None and not r[3]]
    no_response = [r for r in responses if r[3] is None]
    return render_template('event_detail.html',
                           event=event, responses=responses,
                           going=len(going), not_going=len(not_going),
                           no_response=len(no_response))


@app.route('/events/<int:event_id>/rsvp', methods=['POST'])
@login_required
def rsvp(event_id):
    member_id = request.form.get('member_id', type=int)
    action = request.form.get('action')
    if member_id and action in ('yes', 'no'):
        db.set_event_response(event_id, member_id, action == 'yes')
    responses = db.get_event_responses(event_id)
    return render_template('partials/_event_responses.html',
                           event_id=event_id, responses=responses)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@app.route('/profile', methods=['GET'])
@login_required
def profile():
    user_profile = db.get_user_profile(session['user_id'])
    return render_template('profile.html', profile=user_profile, active_tab='profile')


@app.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    email = request.form.get('email', '').strip() or None
    display_name = request.form.get('display_name', '').strip() or None
    initials = request.form.get('initials', '').strip() or None
    font = request.form.get('font', '').strip() or None
    db.update_user_profile(session['user_id'], email, display_name, initials, font)
    session['initials'] = initials or session.get('username', '')
    session['font'] = font or ''
    session['email'] = email or ''
    flash('Profile updated!', 'success')
    return redirect(url_for('profile'))


@app.route('/profile/password', methods=['POST'])
@login_required
def change_password():
    user_profile = db.get_user_profile(session['user_id'])
    username = user_profile[0] if user_profile else session.get('username', '')
    current_pw = request.form.get('current_password', '')
    new_pw = request.form.get('new_password', '')
    confirm = request.form.get('confirm_password', '')
    if not current_pw or not new_pw or not confirm:
        flash('Please fill in all fields.', 'error')
    elif new_pw != confirm:
        flash('Passwords do not match.', 'error')
    elif len(new_pw) < 4:
        flash('Password must be at least 4 characters.', 'error')
    elif not db.authenticate_user(username, current_pw):
        flash('Current password is incorrect.', 'error')
    else:
        db.update_password(session['user_id'], new_pw)
        flash('Password updated!', 'success')
    return redirect(url_for('profile'))


# ---------------------------------------------------------------------------
# User management (admin)
# ---------------------------------------------------------------------------

@app.route('/users')
@admin_required
def user_management():
    users = db.get_all_users()
    departments = db.get_all_departments()
    secondary_depts = db.get_all_secondary_departments_map()
    return render_template('users.html', all_users=users,
                           departments=departments,
                           secondary_depts=secondary_depts,
                           active_tab='user_management')


@app.route('/users/<int:user_id>/role', methods=['POST'])
@admin_required
def set_user_role(user_id):
    new_role = request.form.get('role')
    if new_role not in ('admin', 'user'):
        flash('Invalid role.', 'error')
        return redirect(url_for('user_management'))
    if user_id == session.get('user_id') and new_role != 'admin':
        flash('You cannot remove your own admin role.', 'error')
        return redirect(url_for('user_management'))
    db.set_user_role(user_id, new_role)
    flash('Role updated.', 'success')
    return redirect(url_for('user_management'))


@app.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@admin_required
def toggle_user_active(user_id):
    db.toggle_user_active(user_id)
    flash('User visibility updated.', 'success')
    return redirect(url_for('user_management'))


@app.route('/users/<int:user_id>/display-name', methods=['POST'])
@admin_required
def set_display_name(user_id):
    display_name = request.form.get('display_name', '').strip()
    if not display_name:
        flash('Name cannot be empty.', 'error')
        return redirect(url_for('user_management'))
    db.update_display_name(user_id, display_name)
    flash('Name updated.', 'success')
    return redirect(url_for('user_management'))


@app.route('/users/<int:user_id>/days-off', methods=['POST'])
@admin_required
def set_days_off(user_id):
    days_off = request.form.get('days_off', type=int)
    if days_off is None or days_off < 0:
        flash('Invalid number of days.', 'error')
        return redirect(url_for('user_management'))
    db.update_days_off(user_id, days_off)
    flash('Days off updated.', 'success')
    return redirect(url_for('user_management'))


@app.route('/users/<int:user_id>/start-date', methods=['POST'])
@admin_required
def set_start_date(user_id):
    start_date_str = request.form.get('start_date')
    if not start_date_str:
        db.update_start_date(user_id, None)
        flash('Start date cleared.', 'success')
    else:
        db.update_start_date(user_id, date.fromisoformat(start_date_str))
        flash('Start date updated.', 'success')
    return redirect(url_for('user_management'))


@app.route('/users/<int:user_id>/password', methods=['POST'])
@admin_required
def admin_change_password(user_id):
    new_pw = request.form.get('new_password', '')
    confirm = request.form.get('confirm_password', '')
    if not new_pw or not confirm:
        flash('Please fill in all password fields.', 'error')
    elif new_pw != confirm:
        flash('Passwords do not match.', 'error')
    elif len(new_pw) < 4:
        flash('Password must be at least 4 characters.', 'error')
    else:
        db.update_password(user_id, new_pw)
        flash('Password changed.', 'success')
    return redirect(url_for('user_management'))


# ---------------------------------------------------------------------------
# Settings (admin)
# ---------------------------------------------------------------------------

@app.route('/settings')
@admin_required
def settings():
    dept_id = session.get('viewing_department_id') or session.get('department_id')
    review_requests = db.get_all_review_requests(department_id=dept_id)
    departments = db.get_all_departments()
    return render_template('settings.html',
                           review_requests=review_requests,
                           departments=departments,
                           active_tab='settings', today=date.today())


@app.route('/settings/holidays')
@admin_required
def settings_holidays():
    period_id = request.args.get('period_id', type=int)
    holidays = db.get_period_holidays(period_id) if period_id else []
    return render_template('partials/_period_holidays.html',
                           holidays=holidays, selected_period_id=period_id,
                           today=date.today())


@app.route('/settings/holidays/<int:holiday_id>/toggle', methods=['POST'])
@admin_required
def toggle_holiday(holiday_id):
    period_id = db.toggle_period_holiday(holiday_id)
    holidays = db.get_period_holidays(period_id) if period_id else []
    return render_template('partials/_period_holidays.html',
                           holidays=holidays, selected_period_id=period_id,
                           today=date.today())


@app.route('/settings/holidays/<int:holiday_id>/name', methods=['POST'])
@admin_required
def update_holiday_name(holiday_id):
    new_name = request.form.get('name', '').strip()
    if not new_name:
        return '', 400
    period_id = db.update_period_holiday_name(holiday_id, new_name)
    holidays = db.get_period_holidays(period_id) if period_id else []
    return render_template('partials/_period_holidays.html',
                           holidays=holidays, selected_period_id=period_id,
                           today=date.today())


@app.route('/settings/holidays/<int:holiday_id>/date', methods=['POST'])
@admin_required
def update_holiday_date(holiday_id):
    new_date = request.form.get('holiday_date')
    if not new_date:
        return '', 400
    period_id = db.update_period_holiday_date(holiday_id, date.fromisoformat(new_date))
    holidays = db.get_period_holidays(period_id) if period_id else []
    return render_template('partials/_period_holidays.html',
                           holidays=holidays, selected_period_id=period_id,
                           today=date.today())


@app.route('/settings/holidays/add', methods=['POST'])
@admin_required
def add_period_holiday():
    period_id = request.form.get('period_id', type=int)
    name = request.form.get('name', '').strip()
    holiday_date = request.form.get('holiday_date')
    if period_id and name and holiday_date:
        db.add_period_holiday(period_id, name, date.fromisoformat(holiday_date))
    holidays = db.get_period_holidays(period_id) if period_id else []
    return render_template('partials/_period_holidays.html',
                           holidays=holidays, selected_period_id=period_id,
                           today=date.today())


@app.route('/settings/holidays/<int:holiday_id>/delete', methods=['DELETE'])
@admin_required
def delete_period_holiday(holiday_id):
    period_id = db.delete_period_holiday(holiday_id)
    holidays = db.get_period_holidays(period_id) if period_id else []
    return render_template('partials/_period_holidays.html',
                           holidays=holidays, selected_period_id=period_id,
                           today=date.today())


# ---------------------------------------------------------------------------
# Departments (admin)
# ---------------------------------------------------------------------------

@app.route('/organisation')
@admin_required
def organisation():
    periods = db.get_holiday_periods()
    period_id = request.args.get('period_id', type=int) or db.get_current_period_id()
    holidays = db.get_period_holidays(period_id) if period_id else []
    departments = db.get_all_departments()
    return render_template('organisation.html', periods=periods,
                           selected_period_id=period_id, holidays=holidays,
                           departments=departments,
                           active_tab='organisation', today=date.today())


@app.route('/pre-admins', methods=['GET', 'POST'])
@login_required
def pre_admins():
    if session.get('email') != 'zeth.odderskov@borsen.dk':
        return redirect(url_for('calendar_redirect'))
    if request.method == 'POST':
        raw = request.form.get('emails', '')
        emails = [line.strip() for line in raw.splitlines() if line.strip()]
        db.set_pre_admin_emails(emails)
        flash('Pre-admin list updated.', 'success')
        return redirect(url_for('pre_admins'))
    emails = db.get_pre_admin_emails()
    return render_template('pre_admins.html', emails=emails, active_tab='pre_admins')


@app.route('/organisation/holidays')
@admin_required
def organisation_holidays():
    period_id = request.args.get('period_id', type=int)
    holidays = db.get_period_holidays(period_id) if period_id else []
    return render_template('partials/_period_holidays.html',
                           holidays=holidays, selected_period_id=period_id,
                           today=date.today())


@app.route('/departments', methods=['POST'])
@admin_required
def create_department():
    name = request.form.get('name', '').strip()
    if not name:
        flash('Please enter a department name.', 'error')
        return redirect(url_for('organisation'))
    success, msg = db.create_department(name)
    flash(msg, 'success' if success else 'error')
    return redirect(url_for('organisation'))


@app.route('/departments/<int:dept_id>', methods=['DELETE'])
@admin_required
def delete_department(dept_id):
    db.delete_department(dept_id)
    departments = db.get_all_departments()
    return render_template('partials/_department_list.html',
                           departments=departments)


@app.route('/departments/<int:dept_id>/name', methods=['POST'])
@admin_required
def update_department_name(dept_id):
    name = request.form.get('name', '').strip()
    if name:
        db.update_department_name(dept_id, name)
    departments = db.get_all_departments()
    return render_template('partials/_department_list.html',
                           departments=departments)


@app.route('/departments/<int:dept_id>/fun', methods=['POST'])
@admin_required
def toggle_department_fun(dept_id):
    is_fun = request.form.get('is_fun') == '1'
    db.toggle_department_fun(dept_id, is_fun)
    departments = db.get_all_departments()
    return render_template('partials/_department_list.html',
                           departments=departments)


@app.route('/users/<int:uid>/department', methods=['POST'])
@admin_required
def set_user_department(uid):
    dept_id = request.form.get('department_id', type=int)
    db.set_user_department(uid, dept_id)
    # Remove any secondary assignment that matches the new primary
    if dept_id:
        current_secondary = db.get_user_secondary_departments(uid)
        if dept_id in current_secondary:
            current_secondary.remove(dept_id)
            db.set_user_secondary_departments(uid, current_secondary)
    flash('Department updated.', 'success')
    return redirect(url_for('user_management'))


@app.route('/users/<int:uid>/secondary-departments', methods=['POST'])
@admin_required
def set_user_secondary_departments(uid):
    dept_ids = request.form.getlist('secondary_department_ids', type=int)
    primary = db.get_user_department_id(uid)
    dept_ids = [d for d in dept_ids if d != primary]
    db.set_user_secondary_departments(uid, dept_ids)
    flash('Secondary departments updated.', 'success')
    return redirect(url_for('user_management'))


@app.route('/users/<int:uid>/delete', methods=['POST'])
@admin_required
def delete_user(uid):
    if uid == session.get('user_id'):
        flash('You cannot delete yourself.', 'error')
        return redirect(url_for('user_management'))
    db.delete_user(uid)
    flash('User deleted.', 'success')
    return redirect(url_for('user_management'))


# ---------------------------------------------------------------------------
# Review requests
# ---------------------------------------------------------------------------

@app.route('/review-requests', methods=['POST'])
@admin_required
def create_review_request():
    title = request.form.get('title', '').strip()
    start_date_str = request.form.get('start_date')
    end_date_str = request.form.get('end_date')
    dept_id = request.form.get('department_id', type=int)
    if not title or not start_date_str or not end_date_str or not dept_id:
        flash('Please fill in all fields.', 'error')
        return redirect(url_for('settings'))
    color = request.form.get('color', '#f59e0b').strip()
    start = date.fromisoformat(start_date_str)
    end = date.fromisoformat(end_date_str)
    if start > end:
        flash('End date must be after start date.', 'error')
        return redirect(url_for('settings'))
    db.create_review_request(title, start, end, session['user_id'], department_id=dept_id, color=color)
    db.insert_operation_log(session['user_id'], 'review_request',
                            f'Created review request: {title}')
    flash('Review request created.', 'success')
    return redirect(url_for('settings'))


@app.route('/review-requests/<int:request_id>/toggle', methods=['POST'])
@admin_required
def toggle_review_request(request_id):
    db.toggle_review_request_active(request_id)
    dept_id = session.get('viewing_department_id') or session.get('department_id')
    review_requests = db.get_all_review_requests(department_id=dept_id)
    return render_template('partials/_review_requests_admin.html',
                           review_requests=review_requests, today=date.today())


@app.route('/review-requests/<int:request_id>', methods=['DELETE'])
@admin_required
def delete_review_request(request_id):
    db.delete_review_request(request_id)
    dept_id = session.get('viewing_department_id') or session.get('department_id')
    review_requests = db.get_all_review_requests(department_id=dept_id)
    return render_template('partials/_review_requests_admin.html',
                           review_requests=review_requests, today=date.today())


@app.route('/review-requests/<int:request_id>/color', methods=['POST'])
@admin_required
def update_review_request_color(request_id):
    color = request.form.get('color', '').strip()
    if not color:
        return '', 400
    db.update_review_request_color(request_id, color)
    dept_id = session.get('viewing_department_id') or session.get('department_id')
    review_requests = db.get_all_review_requests(department_id=dept_id)
    return render_template('partials/_review_requests_admin.html',
                           review_requests=review_requests, today=date.today())


@app.route('/review-requests/<int:request_id>/title', methods=['POST'])
@admin_required
def update_review_request_title(request_id):
    title = request.form.get('title', '').strip()
    if not title:
        return '', 400
    db.update_review_request_title(request_id, title)
    dept_id = session.get('viewing_department_id') or session.get('department_id')
    review_requests = db.get_all_review_requests(department_id=dept_id)
    return render_template('partials/_review_requests_admin.html',
                           review_requests=review_requests, today=date.today())


@app.route('/review-requests/<int:request_id>/status')
@admin_required
def review_request_status(request_id):
    review_status = db.get_review_request_status(request_id)
    return render_template('partials/_review_status.html',
                           review_status=review_status)


@app.route('/review-requests/<int:request_id>/seen', methods=['POST'])
@login_required
def mark_review_seen(request_id):
    db.mark_review_seen(request_id, session['user_id'])
    return '', 204


@app.route('/review-requests/<int:request_id>/sign-off', methods=['POST'])
@login_required
def sign_off_review(request_id):
    db.mark_review_decided(request_id, session['user_id'])
    flash('Review signed off!', 'success')
    return redirect(request.referrer or url_for('calendar_redirect'))


@app.route('/review-requests/<int:request_id>/undo-sign-off', methods=['POST'])
@login_required
def undo_sign_off_review(request_id):
    db.undo_review_decided(request_id, session['user_id'])
    flash('Sign-off withdrawn.', 'success')
    return redirect(url_for('my_vacations'))


# ---------------------------------------------------------------------------
# Logs (admin)
# ---------------------------------------------------------------------------

@app.route('/logs')
@admin_required
def logs():
    user_id = request.args.get('user_id', type=int)
    operation_type = request.args.get('operation_type')
    entries = db.get_operation_log(limit=200, user_id=user_id, operation_type=operation_type)
    users = db.get_all_users_basic()
    return render_template('logs.html', entries=entries, users=users,
                           filter_user_id=user_id, filter_operation_type=operation_type,
                           active_tab='logs')


# ---------------------------------------------------------------------------
# Theme toggle
# ---------------------------------------------------------------------------

@app.route('/theme/toggle', methods=['POST'])
@login_required
def toggle_theme():
    current = session.get('theme', 'light')
    new_theme = 'dark' if current == 'light' else 'light'
    session['theme'] = new_theme
    if session.get('user_id'):
        db.update_user_theme(session['user_id'], new_theme)
    resp = make_response('', 200)
    resp.headers['HX-Redirect'] = request.referrer or '/calendar'
    return resp
