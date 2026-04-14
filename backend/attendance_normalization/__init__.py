"""Attendance normalization logic migrated from the browser-side adapter."""

from .aggregator import (
    AttendanceAggregationRecord,
    ZoomMeeting,
    ZoomSegment,
    aggregate_meeting,
)
from .meeting_selection import (
    filter_meetings_by_courses,
    is_uppercase_course_name,
    preselected_course_names,
)
from .temporal_markers import BreakWindow, detect_break_window, snap_effective_start

from .presence_rules import (
    STATUS_ABSENT,
    STATUS_FIRST_HALF,
    STATUS_PRESENT,
    STATUS_SECOND_HALF,
    determine_presence_status,
)

__all__ = [
    "STATUS_ABSENT",
    "STATUS_FIRST_HALF",
    "STATUS_PRESENT",
    "STATUS_SECOND_HALF",
    "AttendanceAggregationRecord",
    "BreakWindow",
    "ZoomMeeting",
    "ZoomSegment",
    "aggregate_meeting",
    "detect_break_window",
    "filter_meetings_by_courses",
    "is_uppercase_course_name",
    "determine_presence_status",
    "preselected_course_names",
    "snap_effective_start",
]
