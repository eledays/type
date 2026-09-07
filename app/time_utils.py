from __future__ import annotations

from datetime import datetime, timezone


UTC = timezone.utc


def utc_now() -> datetime:
    """Return a timezone-aware current instant in UTC."""
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """Normalize persisted timestamps, treating legacy naive values as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
