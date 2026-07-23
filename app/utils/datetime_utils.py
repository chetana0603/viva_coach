"""UTC in the database; IST only for display."""
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def utc_now() -> datetime:
    return datetime.utcnow()


def to_ist_string(dt, fmt="%d %b %Y, %I:%M %p"):
    if dt is None:
        return "-"
    aware = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    return aware.astimezone(IST).strftime(fmt) + " IST"


def from_local_input(value: str):
    """Parse a datetime-local form value (entered as IST) into naive UTC."""
    if not value:
        return None
    dt = datetime.strptime(value, "%Y-%m-%dT%H:%M").replace(tzinfo=IST)
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def to_local_input(dt):
    if dt is None:
        return ""
    aware = dt.replace(tzinfo=timezone.utc)
    return aware.astimezone(IST).strftime("%Y-%m-%dT%H:%M")
