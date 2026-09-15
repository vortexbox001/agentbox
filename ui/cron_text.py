"""One shared cron-to-text helper for the schedules/sensors column (FR-016, research R6).

Turns a five-field cron expression into a human-readable label ("Every day at 7:00 AM") for
the pill in the agents list. The label is rendered **server-side** so it ships with first paint
and is identical wherever a schedule is shown. Times are read in the box timezone
(``os.environ.get("TZ") or "UTC"`` — the same source as the factory's ``cron_timezone()``), never
the browser's zone: the cron's own fields already denote local wall-clock time (the orchestrator
sets each schedule's ``execution_timezone`` to the box tz), so the helper describes those fields
directly without converting them.

A bounded helper covers the daily/weekly/interval patterns the box uses (research R6 rejected a
heavyweight cron library — it risks egress and delays the label to after paint); anything it does
not recognise falls back to the raw expression so the cell is never blank.
"""
from __future__ import annotations

import os

_DAYS = {
    "0": "Sunday", "1": "Monday", "2": "Tuesday", "3": "Wednesday",
    "4": "Thursday", "5": "Friday", "6": "Saturday", "7": "Sunday",
}
_MONTHS = {
    "1": "January", "2": "February", "3": "March", "4": "April", "5": "May", "6": "June",
    "7": "July", "8": "August", "9": "September", "10": "October", "11": "November",
    "12": "December",
}


def box_timezone() -> str:
    """The timezone crons are read in — the box's ``TZ``, falling back to UTC (R6)."""
    return os.environ.get("TZ") or "UTC"


def _clock(minute: str, hour: str) -> str | None:
    """A 12-hour "H:MM AM/PM" label from single-value minute/hour fields, else None."""
    if not (minute.isdigit() and hour.isdigit()):
        return None
    m, h = int(minute), int(hour)
    if not (0 <= m < 60 and 0 <= h < 24):
        return None
    suffix = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {suffix}"


def _day_phrase(dow: str) -> str | None:
    """A "on Monday" / "on weekdays" phrase from the day-of-week field, else None."""
    if dow in ("1-5",):
        return "on weekdays"
    if dow in ("0,6", "6,0", "0-6"):  # 0-6 is every day; handled by caller as daily
        return "on weekends" if dow != "0-6" else None
    if dow.isdigit() and dow in _DAYS:
        return f"on {_DAYS[dow]}"
    return None


def cron_text(expr) -> str:
    """Human-readable label for a five-field cron expression (FR-016).

    Examples: ``0 7 * * *`` → "Every day at 7:00 AM"; ``30 2 * * 1-5`` → "At 2:30 AM on
    weekdays"; ``*/30 * * * *`` → "Every 30 minutes". An unrecognised or malformed expression
    returns the raw string so the cell always shows something.
    """
    if not isinstance(expr, str) or not expr.strip():
        return ""
    raw = expr.strip()
    parts = raw.split()
    if len(parts) != 5:
        return raw
    minute, hour, dom, month, dow = parts

    # Interval on minutes ("*/N * * * *").
    if minute.startswith("*/") and hour == "*" and dom == "*" and month == "*" and dow == "*":
        n = minute[2:]
        if n.isdigit():
            return f"Every {n} minutes"

    # Interval on hours (top of the hour, "0 */N * * *").
    if minute.isdigit() and hour.startswith("*/") and dom == "*" and month == "*" and dow == "*":
        n = hour[2:]
        if n.isdigit():
            return f"Every {n} hours"

    # Every hour at a fixed minute ("M * * * *").
    if minute.isdigit() and hour == "*" and dom == "*" and month == "*" and dow == "*":
        return f"Every hour at :{int(minute):02d}"

    clock = _clock(minute, hour)
    if clock is None:
        return raw

    # Monthly on a fixed day-of-month ("M H D * *").
    if dom.isdigit() and month == "*" and dow == "*":
        return f"On day {int(dom)} of every month at {clock}"

    # Yearly-ish on a fixed month/day ("M H D Mon *").
    if dom.isdigit() and month in _MONTHS and dow == "*":
        return f"On {_MONTHS[month]} {int(dom)} at {clock}"

    # Daily (no day-of-week/day-of-month restriction).
    if dom == "*" and month == "*" and dow == "*":
        return f"Every day at {clock}"

    # Weekly / weekday-scoped on a day-of-week field.
    if dom == "*" and month == "*":
        phrase = _day_phrase(dow)
        if phrase:
            return f"At {clock} {phrase}"

    return raw
