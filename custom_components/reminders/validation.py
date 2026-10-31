"""Field validators for Reminders actions."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any

import voluptuous as vol

from homeassistant.util import dt as dt_util

# Date and time are both required. Seconds, fractional seconds and the UTC
# offset are optional. "T" or a space may separate date and time.
_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}"
    r"(?::\d{2}(?:\.\d{1,6})?)?"
    r"(?:Z|[+-]\d{2}:?\d{2})?$"
)


def trigger_time(value: Any) -> str:
    """Validate a date/time and return it as a string that includes an offset.

    A value without an offset is taken as Home Assistant's local time.
    The result looks like "2026-10-31 11:33:10.095534-04:00" (the fraction
    is left out when there is none).
    """
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        if not _DATETIME_RE.match(text):
            raise vol.Invalid(
                f"'{value}' is not a date and time "
                "(expected e.g. 2026-10-31 11:33 or 2026-10-31 11:33:10-04:00)"
            )
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as err:
            raise vol.Invalid(f"'{value}' is not a valid date and time: {err}") from err
    else:
        raise vol.Invalid(f"'{value}' is not a date and time")

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_util.get_default_time_zone())

    return parsed.isoformat(sep=" ")


def whole_days(value: Any) -> int:
    """Validate a whole number of days, 0 or more (0 = do not repeat)."""
    if isinstance(value, bool):
        raise vol.Invalid(f"'{value}' is not a whole number of days")
    if isinstance(value, int):
        days = value
    elif isinstance(value, float) and value.is_integer():
        days = int(value)
    elif isinstance(value, str) and value.strip().isdigit():
        days = int(value.strip())
    else:
        raise vol.Invalid(f"'{value}' is not a whole number of days")
    if days < 0:
        raise vol.Invalid(f"repeat_frequency cannot be negative (got {days})")
    return days


def non_empty_text(value: Any) -> str:
    """Validate reminder text: a string that is not blank."""
    if not isinstance(value, str) or not value.strip():
        raise vol.Invalid("reminder text cannot be empty")
    return value
