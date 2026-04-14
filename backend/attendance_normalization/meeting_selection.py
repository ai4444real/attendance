"""Meeting/course selection rules migrated from the browser-side adapter."""

from __future__ import annotations

from typing import Iterable

from .aggregator import ZoomMeeting


def is_uppercase_course_name(course_name: str) -> bool:
    letters = "".join(ch for ch in course_name if ch.isalpha())
    return bool(letters) and letters == letters.upper()


def preselected_course_names(meetings: Iterable[ZoomMeeting]) -> list[str]:
    unique_names = {meeting.course or "(senza nome)" for meeting in meetings}
    selected = [name for name in unique_names if is_uppercase_course_name(name)]
    return sorted(selected, key=lambda value: value.lower())


def filter_meetings_by_courses(
    meetings: Iterable[ZoomMeeting],
    selected_course_names: set[str],
) -> list[ZoomMeeting]:
    return [
        meeting
        for meeting in meetings
        if (meeting.course or "(senza nome)") in selected_course_names
    ]
