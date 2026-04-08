from datetime import date, timedelta


def _easter_sunday(year):
    """Compute Easter Sunday using the Anonymous Gregorian algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def get_danish_holidays(year):
    """Return list of (name, date) for Danish public holidays in the given year.

    Excludes Grundlovsdag (not a public holiday for this organisation).
    Includes the day after Kristi Himmelfartsdag.
    Store Bededag abolished from 2024 onwards.
    """
    easter = _easter_sunday(year)
    holidays = [
        ("Nyt\u00e5rsdag",                    date(year, 1, 1)),
        ("Sk\u00e6rtorsdag",                  easter - timedelta(days=3)),
        ("Langfredag",                         easter - timedelta(days=2)),
        ("2. P\u00e5skedag",                  easter + timedelta(days=1)),
        ("Kristi Himmelfartsdag",              easter + timedelta(days=39)),
        ("Dagen efter Kr. Himmelfartsdag",     easter + timedelta(days=40)),
        ("2. Pinsedag",                        easter + timedelta(days=50)),
        ("Juledag",                            date(year, 12, 25)),
        ("2. Juledag",                         date(year, 12, 26)),
    ]
    if year <= 2023:
        holidays.append(("Store Bededag", easter + timedelta(days=26)))
        holidays.sort(key=lambda h: h[1])
    return holidays
