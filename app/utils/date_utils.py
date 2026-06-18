"""
Date/Time Utility Functions
"""
import re
from datetime import datetime, timezone, timedelta
from typing import Optional



def parse_flexible_date(value) -> Optional[datetime]:
    """Best-effort parse of inconsistent posted-date formats from
    different Apify actors (ISO strings, 'X days ago', epoch ints/ms,
    plain dates). Returns None when genuinely unparseable."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        try:
            dt = datetime.utcfromtimestamp(value / 1000 if value > 1e12 else value)
        except (ValueError, OSError, OverflowError):
            return None
    else:
        text = str(value).strip()
        relative = re.match(r'(\d+)\s*(hour|day|week|month)s?\s*ago', text.lower())
        if relative:
            amount, unit = int(relative.group(1)), relative.group(2)
            delta = {
                "hour": timedelta(hours=amount),
                "day": timedelta(days=amount),
                "week": timedelta(weeks=amount),
                "month": timedelta(days=amount * 30),
            }[unit]
            return datetime.utcnow() - delta
        dt = None
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        if dt is None:
            try:
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                return None
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    # Naukri jaise scrapers kabhi-kabhi placeholder "1970-01-01" bhejte
    # hain jab unko actual date nahi mili — usko "unknown" treat karo,
    # "30 saal purani" nahi.
    if dt.year <= 1971 or dt.year > datetime.utcnow().year + 1:
        return None
    return dt


def week_bucket(posted_value, reference: Optional[datetime] = None) -> int:
    """1 = posted in last 7 days, 2 = 8-14 days, 3 = 15-21, 4 = 22-28, 5 = older/unknown."""
    dt = parse_flexible_date(posted_value)
    if dt is None:
        return 5
    reference = reference or datetime.utcnow()
    days = (reference - dt).days
    if days <= 7:
        return 1
    if days <= 14:
        return 2
    if days <= 21:
        return 3
    if days <= 28:
        return 4
    return 5


def recency_label(posted_value) -> str:
    labels = {
        1: "Posted this week",
        2: "Posted 2 weeks ago",
        3: "Posted 3 weeks ago",
        4: "Posted 4 weeks ago",
        5: "Posted over a month ago / date unknown",
    }
    return labels[week_bucket(posted_value)]

def is_recently_posted(posted_value, max_age_days: int = 30) -> bool:
    """True if posting is within max_age_days. If date can't be determined
    at all, default to keep — better than silently dropping a genuinely
    fresh job whose scraper didn't return a clean date."""
    dt = parse_flexible_date(posted_value)
    if dt is None:
        return True
    return (datetime.utcnow() - dt).days <= max_age_days


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