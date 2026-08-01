from __future__ import annotations

from pathlib import Path
from typing import Iterable

from attendance_app.database import access_event_rows, attendance_rows, database_session, initialize_database, list_employees


def export_workbook(db_path: str | Path, workbook_path: str | Path) -> Path:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError as exc:
        raise RuntimeError("openpyxl is required to write attendance.xlsx. Run: pip install -r requirements.txt") from exc

    workbook_path = Path(workbook_path)
    workbook_path.parent.mkdir(parents=True, exist_ok=True)

    with database_session(db_path) as conn:
        initialize_database(conn)
        employees = list_employees(conn)
        attendance = attendance_rows(conn)
        events = access_event_rows(conn)

    workbook = Workbook()
    employee_sheet = workbook.active
    employee_sheet.title = "Employees"
    _write_sheet(
        employee_sheet,
        ["Employee ID", "Name", "Active", "Face Encodings"],
        ([row["employee_id"], row["name"], "Yes" if row["active"] else "No", row["encoding_count"]] for row in employees),
    )

    attendance_sheet = workbook.create_sheet("Daily Attendance")
    _write_sheet(
        attendance_sheet,
        ["Date", "Employee ID", "Name", "Check In", "Check Out", "Check In Source", "Check Out Source", "Updated At"],
        (
            [
                row["attendance_date"],
                row["employee_id"],
                row["name"],
                _time_only(row["check_in"]),
                _time_only(row["check_out"]),
                row["check_in_source"],
                row["check_out_source"],
                row["updated_at"],
            ]
            for row in attendance
        ),
    )

    event_sheet = workbook.create_sheet("Access Events")
    _write_sheet(
        event_sheet,
        ["Event Time", "Employee ID", "Name", "Mode", "Status", "Message", "Distance", "Camera", "Source"],
        (
            [
                row["event_time"],
                row["employee_id"],
                row["employee_name"],
                row["mode"],
                row["status"],
                row["message"],
                row["distance"],
                row["camera_index"],
                row["source"],
            ]
            for row in events
        ),
    )

    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(color="FFFFFF", bold=True)
    for sheet in workbook.worksheets:
        for cell in sheet[1]:
            cell.fill = header_fill
            cell.font = header_font
        sheet.freeze_panes = "A2"
        _autosize_columns(sheet, get_column_letter)

    workbook.save(workbook_path)
    return workbook_path


def _write_sheet(sheet, headers: list[str], rows: Iterable[list]) -> None:
    sheet.append(headers)
    for row in rows:
        sheet.append(row)


def _time_only(value: str | None) -> str | None:
    if not value:
        return None
    try:
        from datetime import datetime

        return datetime.fromisoformat(value).strftime("%H:%M:%S")
    except ValueError:
        return value[-8:]


def _autosize_columns(sheet, get_column_letter) -> None:
    for column in sheet.columns:
        width = 12
        for cell in column:
            if cell.value is not None:
                width = max(width, min(len(str(cell.value)) + 2, 45))
        sheet.column_dimensions[get_column_letter(column[0].column)].width = width
