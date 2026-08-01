from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from attendance_app.database import (
    EncodingRecord,
    attendance_rows,
    database_session,
    fetch_known_faces,
    initialize_database,
    record_attendance,
    replace_face_encodings,
)
from attendance_app.roster import generate_roster, read_roster


class DatabaseTests(unittest.TestCase):
    def test_encoding_replacement_and_employee_listing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "attendance.db"
            with database_session(db_path) as conn:
                initialize_database(conn)
                count = replace_face_encodings(
                    conn,
                    [
                        EncodingRecord("EMP001", "John Doe", "EMP001_John_Doe.jpg", [0.1, 0.2, 0.3]),
                        EncodingRecord("EMP001", "John Doe", "EMP001_John_Doe_2.jpg", [0.4, 0.5, 0.6]),
                    ],
                )
                faces = fetch_known_faces(conn)

            self.assertEqual(count, 2)
            self.assertEqual(len(faces), 2)
            self.assertEqual(faces[0]["employee_id"], "EMP001")

    def test_daily_check_in_and_check_out_are_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "attendance.db"
            first = datetime(2026, 8, 1, 8, 30, tzinfo=timezone.utc)
            duplicate = datetime(2026, 8, 1, 9, 15, tzinfo=timezone.utc)
            leaving = datetime(2026, 8, 1, 17, 45, tzinfo=timezone.utc)
            leaving_again = datetime(2026, 8, 1, 18, 5, tzinfo=timezone.utc)

            with database_session(db_path) as conn:
                initialize_database(conn)
                record_attendance(conn, "EMP001", "John Doe", "entrance", event_time=first)
                second_result = record_attendance(conn, "EMP001", "John Doe", "entrance", event_time=duplicate)
                record_attendance(conn, "EMP001", "John Doe", "exit", event_time=leaving)
                fourth_result = record_attendance(conn, "EMP001", "John Doe", "exit", event_time=leaving_again)
                rows = attendance_rows(conn)

            self.assertEqual(second_result.action, "already_checked_in")
            self.assertEqual(fourth_result.action, "already_checked_out")
            self.assertEqual(len(rows), 1)
            self.assertTrue(rows[0]["check_in"].endswith("08:30:00+00:00"))
            self.assertTrue(rows[0]["check_out"].endswith("17:45:00+00:00"))

    def test_roster_generation_from_plain_image_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_dir = Path(temp_dir) / "images"
            image_dir.mkdir()
            (image_dir / "Jane Smith.jpg").write_bytes(b"not a real image")
            roster_path = Path(temp_dir) / "employees.csv"

            count = generate_roster(image_dir=image_dir, roster_path=roster_path)
            entries = read_roster(roster_path, image_dir)

            self.assertEqual(count, 1)
            self.assertEqual(entries[0].employee_id, "EMP001")
            self.assertEqual(entries[0].name, "Jane Smith")
            self.assertEqual(entries[0].source_image, "Jane Smith.jpg")


if __name__ == "__main__":
    unittest.main()
