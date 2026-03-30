# saskan_lore/tools/utils/stamps.py
"""Timestamp utilities (UTC only)."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(UTC)


def iso_timestamp() -> str:
    """Return the current UTC time as an ISO 8601 string with millisecond precision."""
    return datetime.now(UTC).isoformat(timespec="milliseconds")
