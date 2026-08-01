from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Iterable, Sequence

from attendance_app.config import now_local


@dataclass(frozen=True)
class EncodingRecord:
    employee_id: str
    name: str
    source_image: str
    encoding: Sequence[float]


@dataclass(frozen=True)
class AttendanceResult:
    employee_id: str
    mode: str
    action: str
    message: str
    access_granted: bool
    event_time: datetime


def connect(db_path: str | Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def database_session(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


def initialize_database(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS employees (
            employee_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS face_encodings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            source_image TEXT NOT NULL,
            encoding_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(employee_id, source_image),
            FOREIGN KEY(employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            attendance_date TEXT NOT NULL,
            check_in TEXT,
            check_out TEXT,
            check_in_source TEXT,
            check_out_source TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(employee_id, attendance_date),
            FOREIGN KEY(employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS access_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT,
            employee_name TEXT,
            mode TEXT NOT NULL,
            event_time TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT NOT NULL,
            distance REAL,
            camera_index INTEGER,
            source TEXT,
            FOREIGN KEY(employee_id) REFERENCES employees(employee_id) ON DELETE SET NULL
        );
        """
    )
    conn.commit()


def upsert_employee(conn: sqlite3.Connection, employee_id: str, name: str, event_time: datetime | None = None) -> None:
    event_time = event_time or now_local()
    timestamp = event_time.isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO employees(employee_id, name, active, created_at, updated_at)
        VALUES (?, ?, 1, ?, ?)
        ON CONFLICT(employee_id) DO UPDATE SET
            name = excluded.name,
            active = 1,
            updated_at = excluded.updated_at
        """,
        (employee_id, name, timestamp, timestamp),
    )


def replace_face_encodings(conn: sqlite3.Connection, records: Iterable[EncodingRecord]) -> int:
    records = list(records)
    event_time = now_local()
    timestamp = event_time.isoformat(timespec="seconds")
    with conn:
        conn.execute("DELETE FROM face_encodings")
        for record in records:
            upsert_employee(conn, record.employee_id, record.name, event_time)
            conn.execute(
                """
                INSERT INTO face_encodings(employee_id, source_image, encoding_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    record.employee_id,
                    record.source_image,
                    json.dumps([float(value) for value in record.encoding]),
                    timestamp,
                ),
            )
    return len(records)


def fetch_known_faces(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT e.employee_id, e.name, f.source_image, f.encoding_json
        FROM face_encodings f
        JOIN employees e ON e.employee_id = f.employee_id
        WHERE e.active = 1
        ORDER BY e.employee_id, f.source_image
        """
    ).fetchall()
    return [
        {
            "employee_id": row["employee_id"],
            "name": row["name"],
            "source_image": row["source_image"],
            "encoding": json.loads(row["encoding_json"]),
        }
        for row in rows
    ]


def list_employees(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT e.employee_id, e.name, e.active, COUNT(f.id) AS encoding_count
        FROM employees e
        LEFT JOIN face_encodings f ON f.employee_id = e.employee_id
        GROUP BY e.employee_id, e.name, e.active
        ORDER BY e.employee_id
        """
    ).fetchall()


def attendance_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT a.attendance_date, a.employee_id, e.name, a.check_in, a.check_out,
               a.check_in_source, a.check_out_source, a.updated_at
        FROM attendance a
        JOIN employees e ON e.employee_id = a.employee_id
        ORDER BY a.attendance_date DESC, e.name
        """
    ).fetchall()


def access_event_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT event_time, employee_id, employee_name, mode, status, message, distance, camera_index, source
        FROM access_events
        ORDER BY event_time DESC, id DESC
        LIMIT 5000
        """
    ).fetchall()


def record_attendance(
    conn: sqlite3.Connection,
    employee_id: str,
    name: str,
    mode: str,
    *,
    event_time: datetime | None = None,
    source: str = "webcam",
    camera_index: int | None = None,
    distance: float | None = None,
) -> AttendanceResult:
    if mode not in {"entrance", "exit"}:
        raise ValueError("mode must be 'entrance' or 'exit'")

    event_time = event_time or now_local()
    attendance_date = event_time.date().isoformat()
    timestamp = event_time.isoformat(timespec="seconds")

    with conn:
        upsert_employee(conn, employee_id, name, event_time)
        existing = conn.execute(
            "SELECT * FROM attendance WHERE employee_id = ? AND attendance_date = ?",
            (employee_id, attendance_date),
        ).fetchone()

        if mode == "entrance":
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO attendance(employee_id, attendance_date, check_in, check_in_source, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (employee_id, attendance_date, timestamp, source, timestamp, timestamp),
                )
                action = "checked_in"
                message = f"ACCESS GRANTED - IN {event_time.strftime('%H:%M:%S')}"
            elif existing["check_in"]:
                action = "already_checked_in"
                message = f"ACCESS GRANTED - IN ALREADY {_clock_time(existing['check_in'])}"
            else:
                conn.execute(
                    """
                    UPDATE attendance
                    SET check_in = ?, check_in_source = ?, updated_at = ?
                    WHERE employee_id = ? AND attendance_date = ?
                    """,
                    (timestamp, source, timestamp, employee_id, attendance_date),
                )
                action = "checked_in"
                message = f"ACCESS GRANTED - IN {event_time.strftime('%H:%M:%S')}"
        else:
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO attendance(employee_id, attendance_date, check_out, check_out_source, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (employee_id, attendance_date, timestamp, source, timestamp, timestamp),
                )
                action = "checked_out_without_check_in"
                message = f"EXIT RECORDED - OUT {event_time.strftime('%H:%M:%S')}"
            elif existing["check_out"]:
                action = "already_checked_out"
                message = f"EXIT ALREADY {_clock_time(existing['check_out'])}"
            else:
                conn.execute(
                    """
                    UPDATE attendance
                    SET check_out = ?, check_out_source = ?, updated_at = ?
                    WHERE employee_id = ? AND attendance_date = ?
                    """,
                    (timestamp, source, timestamp, employee_id, attendance_date),
                )
                action = "checked_out"
                message = f"EXIT RECORDED - OUT {event_time.strftime('%H:%M:%S')}"

        conn.execute(
            """
            INSERT INTO access_events(employee_id, employee_name, mode, event_time, status, message, distance, camera_index, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (employee_id, name, mode, timestamp, action, message, distance, camera_index, source),
        )

    return AttendanceResult(
        employee_id=employee_id,
        mode=mode,
        action=action,
        message=message,
        access_granted=True,
        event_time=event_time,
    )


def _clock_time(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%H:%M:%S")
    except ValueError:
        return value[-8:]


def log_unknown_face(
    conn: sqlite3.Connection,
    *,
    mode: str,
    message: str = "ACCESS DENIED - UNKNOWN",
    event_time: datetime | None = None,
    source: str = "webcam",
    camera_index: int | None = None,
    distance: float | None = None,
) -> None:
    event_time = event_time or now_local()
    timestamp = event_time.isoformat(timespec="seconds")
    with conn:
        conn.execute(
            """
            INSERT INTO access_events(employee_id, employee_name, mode, event_time, status, message, distance, camera_index, source)
            VALUES (NULL, NULL, ?, ?, 'unknown', ?, ?, ?, ?)
            """,
            (mode, timestamp, message, distance, camera_index, source),
        )
