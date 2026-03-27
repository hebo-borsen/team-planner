from datetime import date

from app import (
    add_holiday,
    add_holiday_range,
    get_holidays_for_month,
    get_all_holidays,
    delete_holiday,
)


def test_add_holiday():
    success, msg = add_holiday(date(2026, 12, 25), "Christmas")
    assert success is True
    assert "successfully" in msg


def test_add_duplicate_holiday():
    add_holiday(date(2026, 12, 25), "Christmas")
    success, msg = add_holiday(date(2026, 12, 25), "Christmas Again")
    assert success is False
    assert "already exists" in msg


def test_add_holiday_range():
    added, skipped = add_holiday_range(date(2026, 12, 24), date(2026, 12, 26), "Christmas Break")
    assert added == 3
    assert skipped == 0


def test_get_holidays_for_month():
    add_holiday(date(2026, 1, 1), "New Year")
    add_holiday(date(2026, 2, 14), "Valentine's Day")

    holidays = get_holidays_for_month(2026, 1)
    dates = [h[0] for h in holidays]
    assert date(2026, 1, 1) in dates
    assert date(2026, 2, 14) not in dates


def test_get_all_holidays():
    add_holiday(date(2026, 5, 1), "May Day")
    holidays = get_all_holidays()
    names = [h[1] for h in holidays]
    assert "May Day" in names


def test_delete_holiday():
    add_holiday(date(2026, 6, 5), "Constitution Day")
    holidays = get_all_holidays()
    hol_id = next(h[2] for h in holidays if h[1] == "Constitution Day")

    delete_holiday(hol_id)

    holidays = get_all_holidays()
    names = [h[1] for h in holidays]
    assert "Constitution Day" not in names
