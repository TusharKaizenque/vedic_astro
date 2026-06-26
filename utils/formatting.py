"""Presentation helpers — keep raw API/DB values out of user-facing text."""
from datetime import datetime


def format_date(value) -> str:
    """Format an ISO datetime string or datetime into 'October 17, 2026'.

    Returns the original string unchanged if it can't be parsed (never raises)."""
    if isinstance(value, datetime):
        return f"{value.strftime('%B')} {value.day}, {value.year}"
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return str(value)
    # %-d is unix-only; build the day without a leading zero portably.
    return f"{dt.strftime('%B')} {dt.day}, {dt.year}"
