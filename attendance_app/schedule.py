from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time


@dataclass(frozen=True)
class AttendanceSchedule:
    check_in_time: time
    check_out_time: time


def parse_clock_time(value: str) -> time:
    value = value.strip().lower().replace(" ", "")
    formats = ("%H:%M", "%H", "%I:%M%p", "%I%p")
    for time_format in formats:
        try:
            return datetime.strptime(value, time_format).time()
        except ValueError:
            continue
    raise ValueError(f"Invalid time '{value}'. Use 08:00, 16:00, 8am, or 4pm.")


def resolve_attendance_mode(requested_mode: str, event_time: datetime, schedule: AttendanceSchedule) -> str:
    if requested_mode in {"entrance", "exit"}:
        return requested_mode
    if requested_mode != "auto":
        raise ValueError("mode must be 'auto', 'entrance', or 'exit'")

    check_in_delta = _seconds_from_clock(event_time, schedule.check_in_time)
    check_out_delta = _seconds_from_clock(event_time, schedule.check_out_time)
    return "entrance" if check_in_delta <= check_out_delta else "exit"


def describe_schedule(schedule: AttendanceSchedule) -> str:
    return f"in {schedule.check_in_time.strftime('%H:%M')} / out {schedule.check_out_time.strftime('%H:%M')}"


def _seconds_from_clock(event_time: datetime, clock_time: time) -> float:
    anchor = event_time.replace(
        hour=clock_time.hour,
        minute=clock_time.minute,
        second=0,
        microsecond=0,
    )
    return abs((event_time - anchor).total_seconds())

