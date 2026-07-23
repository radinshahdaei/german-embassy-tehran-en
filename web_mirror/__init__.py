"""Crawl, translate, and generate a static mirror of any website."""

from datetime import datetime, timezone


def _now() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


__version__ = "1.0.0"
