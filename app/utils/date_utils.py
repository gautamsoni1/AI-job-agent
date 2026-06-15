"""
Date/Time Utility Functions
"""
from datetime import datetime, timezone, timedelta
from typing import Optional


def utcnow() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


def to_iso(dt: Optional[datetime]) -> Optional[str]:
    """Convert a datetime to ISO 8601 string, or None."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def days_ago(dt: Optional[datetime]) -> Optional[int]:
    """Return number of whole days between dt and now."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = utcnow() - dt
    return delta.days


def start_of_week(reference: Optional[datetime] = None) -> datetime:
    """Return the datetime for the start (Monday 00:00) of the current week."""
    reference = reference or datetime.utcnow()
    start = reference - timedelta(days=reference.weekday())
    return start.replace(hour=0, minute=0, second=0, microsecond=0)


def start_of_day(reference: Optional[datetime] = None) -> datetime:
    """Return midnight of the given (or current) day."""
    reference = reference or datetime.utcnow()
    return reference.replace(hour=0, minute=0, second=0, microsecond=0)


def format_human(dt: Optional[datetime]) -> str:
    """Human-readable date string, e.g. 'Jun 16, 2026'."""
    if dt is None:
        return ""
    return dt.strftime("%b %d, %Y")


def is_within_days(dt: Optional[datetime], days: int) -> bool:
    """Check whether a datetime is within the last `days` days."""
    if dt is None:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (utcnow() - dt) <= timedelta(days=days)


def add_days(dt: datetime, days: int) -> datetime:
    return dt + timedelta(days=days)