from __future__ import annotations

import unittest
from datetime import datetime, timezone

from attendance_app.schedule import AttendanceSchedule, parse_clock_time, resolve_attendance_mode


class ScheduleTests(unittest.TestCase):
    def test_parse_clock_time_accepts_common_formats(self) -> None:
        self.assertEqual(parse_clock_time("08:00").strftime("%H:%M"), "08:00")
        self.assertEqual(parse_clock_time("8am").strftime("%H:%M"), "08:00")
        self.assertEqual(parse_clock_time("4 pm").strftime("%H:%M"), "16:00")

    def test_auto_mode_uses_closest_company_time(self) -> None:
        schedule = AttendanceSchedule(parse_clock_time("08:00"), parse_clock_time("16:00"))

        self.assertEqual(
            resolve_attendance_mode("auto", datetime(2026, 8, 1, 8, 10, tzinfo=timezone.utc), schedule),
            "entrance",
        )
        self.assertEqual(
            resolve_attendance_mode("auto", datetime(2026, 8, 1, 15, 50, tzinfo=timezone.utc), schedule),
            "exit",
        )

    def test_manual_modes_are_respected(self) -> None:
        schedule = AttendanceSchedule(parse_clock_time("08:00"), parse_clock_time("16:00"))

        self.assertEqual(
            resolve_attendance_mode("entrance", datetime(2026, 8, 1, 20, 0, tzinfo=timezone.utc), schedule),
            "entrance",
        )
        self.assertEqual(
            resolve_attendance_mode("exit", datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc), schedule),
            "exit",
        )


if __name__ == "__main__":
    unittest.main()
