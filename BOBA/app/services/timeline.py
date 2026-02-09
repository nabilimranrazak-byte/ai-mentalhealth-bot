from datetime import datetime, timezone

def human_delta(from_dt: datetime | None, to_dt: datetime | None = None) -> str | None:
    if not from_dt:
        return None
    to_dt = to_dt or datetime.now(timezone.utc)
    delta = to_dt - from_dt
    secs = int(delta.total_seconds())
    if secs < 60:
        return "just now"
    mins = secs // 60
    if mins < 60:
        return f"{mins} minute(s) ago"
    hrs = mins // 60
    if hrs < 24:
        return f"{hrs} hour(s) ago"
    days = hrs // 24
    if days < 7:
        return f"{days} day(s) ago"
    weeks = days // 7
    if weeks < 5:
        return f"{weeks} week(s) ago"
    months = days // 30
    if months < 12:
        return f"{months} month(s) ago"
    years = days // 365
    return f"{years} year(s) ago"
