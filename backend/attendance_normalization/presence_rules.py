"""Presence status rules migrated from ``attendance/adapter/js/presence-rules.js``.

This module intentionally mirrors the current browser logic without adding
extra heuristics. The goal of this first migration step is to make the
decision function explicit, testable, and reusable from Python.
"""

STATUS_PRESENT = "presente"
STATUS_FIRST_HALF = "prima_meta"
STATUS_SECOND_HALF = "seconda_meta"
STATUS_ABSENT = "assente"

DEFAULT_THRESHOLD = 0.8


def determine_presence_status(
    minutes_first_half: float,
    minutes_second_half: float,
    duration_first_half: float,
    duration_second_half: float,
    threshold: float = DEFAULT_THRESHOLD,
) -> str:
    """Classify presence exactly like the current JavaScript rule set.

    A participant counts for a half only if:
    - that half has a positive duration;
    - present minutes / half duration >= threshold.

    The final status is:
    - ``presente`` when both halves pass the threshold;
    - ``prima_meta`` when only the first half passes;
    - ``seconda_meta`` when only the second half passes;
    - ``assente`` otherwise.
    """

    first_ok = duration_first_half > 0 and (
        minutes_first_half / duration_first_half
    ) >= threshold
    second_ok = duration_second_half > 0 and (
        minutes_second_half / duration_second_half
    ) >= threshold

    if first_ok and second_ok:
        return STATUS_PRESENT
    if first_ok:
        return STATUS_FIRST_HALF
    if second_ok:
        return STATUS_SECOND_HALF
    return STATUS_ABSENT
