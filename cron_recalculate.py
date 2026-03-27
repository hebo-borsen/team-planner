#!/usr/bin/env python3
"""Nightly cron job: recalculate accrued holiday days for each user."""

import sys
from datetime import date, datetime
import db


def calculate_accrued(days_off_per_year, year):
    """Calculate accrued days based on how far into the year we are."""
    today = date.today()
    day_of_year = today.timetuple().tm_yday
    days_in_year = 366 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 365
    return round(days_off_per_year * day_of_year / days_in_year, 1)


def recalculate_all():
    year = datetime.now().year
    users = db.get_all_users_basic()

    if not users:
        db.insert_operation_log(None, 'holiday_recalculation',
                                'No users found. Nothing to recalculate.')
        print("No users found.")
        return

    print(f"Recalculating holidays for {len(users)} user(s), year={year}")

    for user_id, username in users:
        try:
            summary = db.get_vacation_summary(user_id, year)
            before = summary['accrued']
            after = calculate_accrued(summary['days_off_per_year'], year)

            db.update_accrued_days(user_id, after)

            message = (
                f"User '{username}' (id={user_id}): "
                f"accrued {before} -> {after}, "
                f"entitlement={summary['days_off_per_year']}, "
                f"used={summary['used']}, "
                f"pending={summary['pending']}, "
                f"remaining={summary['remaining']}"
            )
            db.insert_operation_log(user_id, 'holiday_recalculation', message)
            print(f"  {message}")

        except Exception as e:
            error_msg = f"Error recalculating for user '{username}' (id={user_id}): {e}"
            db.insert_operation_log(user_id, 'holiday_recalculation', error_msg)
            print(f"  ERROR: {error_msg}", file=sys.stderr)

    db.insert_operation_log(
        None, 'holiday_recalculation',
        f"Nightly recalculation completed for {len(users)} user(s), year={year}."
    )
    print("Recalculation complete.")


if __name__ == '__main__':
    recalculate_all()
