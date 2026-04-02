from datetime import date

from app import (
    add_team_member,
    get_team_members,
    add_vacation_day,
    add_vacation_range,
    get_all_vacations,
    get_vacations_for_month,
    delete_vacation,
)


def _create_member(name="VacTest"):
    add_team_member(name, "🏖️")
    return next(m[0] for m in get_team_members() if m[1] == name)


def test_add_vacation_day():
    member_id = _create_member()
    success, msg = add_vacation_day(member_id, date(2026, 7, 1))
    assert success is True
    assert "successfully" in msg


def test_add_duplicate_vacation_day():
    member_id = _create_member()
    add_vacation_day(member_id, date(2026, 7, 2))
    success, msg = add_vacation_day(member_id, date(2026, 7, 2))
    assert success is False
    assert "already exists" in msg


def test_add_vacation_range():
    member_id = _create_member()
    added, skipped = add_vacation_range(member_id, date(2026, 8, 3), date(2026, 8, 7))
    assert added == 5
    assert skipped == 0


def test_add_vacation_range_with_overlap():
    member_id = _create_member()
    add_vacation_day(member_id, date(2026, 9, 5))
    added, skipped = add_vacation_range(member_id, date(2026, 9, 3), date(2026, 9, 7))
    assert added == 4
    assert skipped == 1


def test_get_all_vacations():
    member_id = _create_member()
    add_vacation_day(member_id, date(2026, 10, 10))
    vacations = get_all_vacations()
    dates = [v[1] for v in vacations]
    assert date(2026, 10, 10) in dates


def test_get_vacations_for_month():
    member_id = _create_member()
    add_vacation_day(member_id, date(2026, 11, 15))
    add_vacation_day(member_id, date(2026, 12, 1))

    rows = get_vacations_for_month(2026, 11)
    vacation_dates = [r[2] for r in rows if r[2] is not None]
    assert date(2026, 11, 15) in vacation_dates
    assert date(2026, 12, 1) not in vacation_dates


def test_delete_vacation():
    member_id = _create_member()
    add_vacation_day(member_id, date(2026, 6, 20))
    vacations = get_all_vacations()
    vac_id = next(v[2] for v in vacations if v[1] == date(2026, 6, 20))

    delete_vacation(vac_id)

    vacations = get_all_vacations()
    dates = [v[1] for v in vacations]
    assert date(2026, 6, 20) not in dates
