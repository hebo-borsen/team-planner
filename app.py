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
                    session['needs_initial_accrued'] = db.needs_initial_accrued(user[0])
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
            return redirect(url_for('calendar_view'))
        return f(*args, **kwargs)
    return decorated


@app.context_processor
def inject_globals():
    is_admin = session.get('role') == 'admin'
    return {
        'theme': session.get('theme', 'light'),
        'user_id': session.get('user_id'),
        'username': session.get('username', ''),
        'initials': session.get('initials', session.get('username', '')),
        'user_font': session.get('font', ''),
        'is_admin': is_admin,
        'pending_count': db.get_pending_count() if is_admin and session.get('user_id') else 0,
        'active_tab': request.endpoint or '',
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
            session['needs_initial_accrued'] = db.needs_initial_accrued(user[0])
            token = db.create_session_token(user[0])
            resp = redirect(url_for('calendar_view'))
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
        if not shortname or not display_name or not password or not confirm:
            flash('Please fill in all fields.', 'error')
            return redirect(url_for('register'))
        if password != confirm:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('register'))
        if len(password) < 4:
            flash('Password must be at least 4 characters.', 'error')
            return redirect(url_for('register'))
        success, msg = db.register_user(shortname, password, display_name=display_name, email=email, font=font)
        if success:
            flash(msg, 'success')
            return redirect(url_for('login'))
        flash(msg, 'error')
        return redirect(url_for('register'))
    return render_template('register.html')


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
            return redirect(url_for('calendar_view'))
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
        return redirect(url_for('calendar_view'))
    return render_template('initial_accrued.html',
                           period_label=period_label, days_off=days_off,
                           period_start=period_start, period_end=period_end)


# ---------------------------------------------------------------------------
# Calendar (home)
# ---------------------------------------------------------------------------

@app.route('/')
@login_required
def calendar_view():
    today = date.today()

    start_str = request.args.get('from')
    end_str = request.args.get('to')
    start_date = date.fromisoformat(start_str) if start_str else today
    end_date = date.fromisoformat(end_str) if end_str else today + timedelta(days=29)

    users = db.get_all_users_for_calendar()
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
    pending_dict = {}
    removal_dict = {}
    for uid, display, vdate, status in vacations_data:
        if not vdate:
            continue
        if status == 'approved':
            vacation_dict.setdefault(display, set()).add(vdate)
        elif status == 'pending':
            pending_dict.setdefault(display, set()).add(vdate)
        elif status == 'pending_removal':
            removal_dict.setdefault(display, set()).add(vdate)

    weekend_days = set()
    for d in days:
        if d.weekday() in (5, 6):
            weekend_days.add(d)

    total_vacations = db.get_vacation_count()

    # Holiday period summary
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
                    admin_summaries = db.get_all_users_period_summary(pstart, pend)
                break

    if period_start and period_end_date:
        vacation_summary = db.get_vacation_summary(
            session['user_id'], period_start, period_end_date)
    else:
        vacation_summary = {'days_off_per_year': 34, 'used': 0, 'pending': 0,
                            'remaining': 34, 'accrued': 0}

    template_data = {
        'today': today,
        'start_date': start_date,
        'end_date': end_date,
        'days': days,
        'users': users,
        'holiday_dict': holiday_dict,
        'vacation_dict': vacation_dict,
        'pending_dict': pending_dict,
        'removal_dict': removal_dict,
        'weekend_days': weekend_days,
        'total_vacations': total_vacations,
        'vacation_summary': vacation_summary,
        'current_year': today.year,
        'period_summary': period_summary,
        'period_label': period_label,
        'period_end_date': period_end_date,
        'admin_summaries': admin_summaries,
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
        return redirect(url_for('calendar_view'))
    start = date.fromisoformat(vacation_date)
    end = date.fromisoformat(end_date) if end_date else start
    if start > end:
        flash('End date must be after start date.', 'error')
        return redirect(url_for('calendar_view'))
    is_su = session.get('role') == 'admin'
    requester = session.get('username', '')
    added, skipped = db.add_vacation_for_user(user_id, start, end, is_admin=is_su, requested_by=requester)
    if added:
        if is_su:
            flash(f'Added {added} vacation day(s)!', 'success')
        else:
            flash(f'Requested {added} vacation day(s) — pending approval.', 'info')
    if skipped:
        flash(f'Skipped {skipped} duplicate day(s).', 'info')
    referer = request.form.get('redirect') or url_for('calendar_view')
    return redirect(referer)


@app.route('/vacations/<int:vacation_id>', methods=['DELETE'])
@login_required
def delete_vacation(vacation_id):
    if session.get('role') == 'admin':
        db.delete_vacation(vacation_id)
        flash('Vacation day deleted.', 'success')
    else:
        success, msg = db.request_vacation_removal(vacation_id)
        flash(msg, 'info' if success else 'warning')
    return redirect(url_for('calendar_view'))


@app.route('/vacations/remove-by-dates', methods=['POST'])
@login_required
def remove_vacations_by_dates():
    user_id = request.form.get('user_id', type=int)
    start = request.form.get('start_date')
    end = request.form.get('end_date')
    if not user_id or not start or not end:
        flash('Missing parameters.', 'error')
        return redirect(url_for('calendar_view'))
    # Non-admins can only remove their own vacations
    if session.get('role') != 'admin' and user_id != session.get('user_id'):
        flash('You can only remove your own vacations.', 'error')
        return redirect(url_for('calendar_view'))
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    if session.get('role') == 'admin':
        ids = db.get_vacation_ids_for_user_dates(
            user_id, start_date, end_date, ['approved', 'pending', 'pending_removal'])
        if ids:
            deleted = db.delete_vacation_bulk(ids)
            flash(f'Deleted {deleted} vacation day(s).', 'success')
        else:
            flash('No vacation days found in that range.', 'warning')
    else:
        ids = db.get_vacation_ids_for_user_dates(
            user_id, start_date, end_date, ['approved'])
        if ids:
            updated = db.request_vacation_removal_bulk(ids)
            flash(f'Removal requested for {updated} day(s).', 'info')
        else:
            flash('No approved vacation days found in that range.', 'warning')
    return redirect(url_for('calendar_view'))


@app.route('/vacations/approve-by-dates', methods=['POST'])
@admin_required
def approve_vacations_by_dates():
    user_id = request.form.get('user_id', type=int)
    start = request.form.get('start_date')
    end = request.form.get('end_date')
    action = request.form.get('action')
    if not user_id or not start or not end or action not in ('approve', 'reject'):
        flash('Missing parameters.', 'error')
        return redirect(url_for('calendar_view'))
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    ids = db.get_vacation_ids_for_user_dates(user_id, start_date, end_date, ['pending'])
    if not ids:
        flash('No pending requests found in that range.', 'warning')
        return redirect(url_for('calendar_view'))
    if action == 'approve':
        db.approve_vacation_bulk(ids, session['username'])
        flash(f'Approved {len(ids)} vacation day(s).', 'success')
    else:
        db.reject_vacation_bulk(ids)
        flash(f'Rejected {len(ids)} vacation day(s).', 'success')
    return redirect(url_for('calendar_view'))


@app.route('/vacations/export')
@login_required
def export_vacations():
    all_vacations = db.get_all_vacations()
    wb = Workbook()
    ws = wb.active
    ws.title = "Vacations"
    ws.append(["Team Member", "Vacation Date", "Status"])
    for name, vdate, vid, status in all_vacations:
        ws.append([name, format_date(vdate), status])
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    resp = make_response(output.read())
    resp.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    resp.headers['Content-Disposition'] = f'attachment; filename=team_vacations_{datetime.now().strftime("%Y%m%d")}.xlsx'
    return resp


# ---------------------------------------------------------------------------
# Vacation approvals (admin)
# ---------------------------------------------------------------------------

@app.route('/approvals')
@admin_required
def approvals():
    groups = db.get_pending_requests_grouped()
    holidays = db.get_all_enabled_holidays()
    return render_template('approvals.html', groups=groups,
                           holidays=holidays, active_tab='approvals')


def _approval_response():
    groups = db.get_pending_requests_grouped()
    holidays = db.get_all_enabled_holidays()
    if is_htmx():
        return render_template('partials/_approval_list.html',
                               groups=groups, holidays=holidays)
    return redirect(url_for('approvals'))


@app.route('/approvals/<int:vacation_day_id>/approve', methods=['POST'])
@admin_required
def approve_vacation(vacation_day_id):
    db.approve_vacation(vacation_day_id, session['username'])
    if not is_htmx():
        flash('Request approved.', 'success')
    return _approval_response()


@app.route('/approvals/<int:vacation_day_id>/reject', methods=['POST'])
@admin_required
def reject_vacation(vacation_day_id):
    db.reject_vacation(vacation_day_id)
    if not is_htmx():
        flash('Request rejected.', 'success')
    return _approval_response()


@app.route('/approvals/bulk', methods=['POST'])
@admin_required
def bulk_approve():
    ids = request.form.getlist('ids', type=int)
    action = request.form.get('action')
    if ids and action == 'approve':
        db.approve_vacation_bulk(ids, session['username'])
        if not is_htmx():
            flash(f'Approved {len(ids)} day(s).', 'success')
    elif ids and action == 'reject':
        db.reject_vacation_bulk(ids)
        if not is_htmx():
            flash(f'Rejected {len(ids)} day(s).', 'success')
    return _approval_response()


# ---------------------------------------------------------------------------
# My Vacations
# ---------------------------------------------------------------------------

@app.route('/my-vacations')
@login_required
def my_vacations():
    groups = db.get_user_vacations_grouped(session['user_id'])
    holidays = db.get_all_enabled_holidays()
    return render_template('my_vacations.html', groups=groups,
                           holidays=holidays, active_tab='my_vacations')


@app.route('/vacations/<int:vacation_day_id>/request-removal', methods=['POST'])
@login_required
def request_removal(vacation_day_id):
    if session.get('role') == 'admin':
        db.delete_vacation(vacation_day_id)
        flash('Vacation day deleted.', 'success')
    else:
        success, msg = db.request_vacation_removal(vacation_day_id)
        flash(msg, 'info' if success else 'warning')
    return redirect(url_for('my_vacations'))


@app.route('/vacations/<int:vacation_day_id>/cancel', methods=['POST'])
@login_required
def cancel_request(vacation_day_id):
    deleted = db.cancel_pending_request(vacation_day_id, session['username'])
    if deleted:
        flash('Pending request cancelled.', 'success')
    else:
        flash('Could not cancel request.', 'warning')
    return redirect(url_for('my_vacations'))


@app.route('/vacations/bulk-removal', methods=['POST'])
@login_required
def bulk_request_removal():
    ids = request.form.getlist('ids', type=int)
    if not ids:
        flash('No vacation days selected.', 'warning')
        return redirect(url_for('my_vacations'))
    if session.get('role') == 'admin':
        deleted = db.delete_vacation_bulk(ids)
        flash(f'{deleted} vacation day(s) deleted.', 'success')
    else:
        updated = db.request_vacation_removal_bulk(ids)
        flash(f'Removal requested for {updated} day(s).', 'info')
    return redirect(url_for('my_vacations'))


@app.route('/vacations/bulk-cancel', methods=['POST'])
@login_required
def bulk_cancel_request():
    ids = request.form.getlist('ids', type=int)
    if not ids:
        flash('No vacation days selected.', 'warning')
        return redirect(url_for('my_vacations'))
    deleted = db.cancel_pending_request_bulk(ids, session['username'])
    if deleted:
        flash(f'{deleted} pending request(s) cancelled.', 'success')
    else:
        flash('Could not cancel requests.', 'warning')
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
    return render_template('users.html', all_users=users,
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
    periods = db.get_holiday_periods()
    period_id = request.args.get('period_id', type=int) or db.get_current_period_id()
    holidays = db.get_period_holidays(period_id) if period_id else []
    return render_template('settings.html', periods=periods,
                           selected_period_id=period_id, holidays=holidays,
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
    resp.headers['HX-Redirect'] = request.referrer or '/'
    return resp
