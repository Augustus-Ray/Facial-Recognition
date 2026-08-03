from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from attendance_app.config import DEFAULT_PATHS, PROJECT_ROOT
from attendance_app.database import database_session, initialize_database, list_employees
from attendance_app.encoder import generate_encodings
from attendance_app.excel_exporter import export_workbook
from attendance_app.recognizer import run_webcam
from attendance_app.roster import generate_roster
from attendance_app.schedule import AttendanceSchedule, parse_clock_time
from attendance_app.settings import ensure_company_settings, load_company_settings


def project_path(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Company face-recognition attendance system with local real-time database and Excel export."
    )
    parser.add_argument("--db", default=str(DEFAULT_PATHS.database_path), help="SQLite database path.")
    parser.add_argument("--excel", default=str(DEFAULT_PATHS.workbook_path), help="Excel workbook path.")
    parser.add_argument("--attendance-dir", default=str(DEFAULT_PATHS.attendance_dir), help="Daily attendance Excel folder.")
    parser.add_argument("--roster", default=str(DEFAULT_PATHS.roster_path), help="Employee roster CSV path.")
    parser.add_argument("--settings", default=str(DEFAULT_PATHS.settings_path), help="Company settings JSON path.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Create the local database and Excel workbook.")

    encode = subparsers.add_parser("encode", help="Read employee images and store face encodings.")
    encode.add_argument("--images", default=str(DEFAULT_PATHS.image_dir), help="Employee image folder.")
    encode.add_argument("--model", choices=["hog", "cnn"], default="hog", help="Face detector used while encoding.")
    encode.add_argument("--no-excel", action="store_true", help="Skip Excel export after encoding.")

    roster = subparsers.add_parser("roster", help="Create an editable employees.csv from the images folder.")
    roster.add_argument("--images", default=str(DEFAULT_PATHS.image_dir), help="Employee image folder.")
    roster.add_argument("--prefix", default="EMP", help="Employee ID prefix for generated IDs.")
    roster.add_argument("--start", type=int, default=1, help="First generated employee number.")
    roster.add_argument("--force", action="store_true", help="Overwrite an existing roster CSV.")

    run = subparsers.add_parser("run", help="Start real-time webcam attendance recognition.")
    run.add_argument("--mode", choices=["auto", "entrance", "exit"], default="auto", help="Attendance mode.")
    run.add_argument("--check-in-time", help="Auto mode check-in time, such as 08:00 or 8am.")
    run.add_argument("--check-out-time", help="Auto mode check-out time, such as 16:00 or 4pm.")
    run.add_argument("--timezone", help="IANA time zone name, such as America/New_York.")
    run.add_argument("--camera", type=int, default=0, help="OpenCV camera index.")
    run.add_argument("--tolerance", type=float, default=0.50, help="Lower is stricter. Typical range: 0.45-0.60.")
    run.add_argument("--process-every", type=int, default=2, help="Run recognition every N frames.")
    run.add_argument("--scale", type=float, default=0.25, help="Resize factor for faster recognition.")
    run.add_argument("--model", choices=["hog", "cnn"], default="hog", help="Face detector used on webcam frames.")
    run.add_argument("--cooldown", type=int, default=20, help="Seconds before the same employee can log again.")

    subparsers.add_parser("export", help="Rewrite the Excel workbook from the database.")
    subparsers.add_parser("employees", help="List enrolled employees.")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    db_path = project_path(args.db)
    workbook_path = project_path(args.excel)
    attendance_dir = project_path(args.attendance_dir)
    roster_path = project_path(args.roster)
    settings_path = project_path(args.settings)

    try:
        if args.command == "init-db":
            ensure_company_settings(settings_path)
            with database_session(db_path) as conn:
                initialize_database(conn)
            export_workbook(db_path, workbook_path, attendance_dir)
            print(f"Database ready: {db_path}")
            print(f"Excel workbook ready: {workbook_path}")
            print(f"Daily attendance folder ready: {attendance_dir}")

        elif args.command == "encode":
            count = generate_encodings(
                image_dir=project_path(args.images),
                roster_path=roster_path,
                db_path=db_path,
                workbook_path=None if args.no_excel else workbook_path,
                attendance_dir=attendance_dir,
                detection_model=args.model,
            )
            print(f"Stored {count} face encoding(s).")

        elif args.command == "roster":
            count = generate_roster(
                image_dir=project_path(args.images),
                roster_path=roster_path,
                employee_prefix=args.prefix,
                start_number=args.start,
                overwrite=args.force,
            )
            print(f"Roster written: {roster_path}")
            print(f"Mapped {count} image(s). Review employee IDs/names before encoding.")

        elif args.command == "run":
            settings = load_company_settings(settings_path)
            if args.timezone:
                os.environ["ATTENDANCE_TIMEZONE"] = args.timezone
            elif settings.timezone and not os.getenv("ATTENDANCE_TIMEZONE"):
                os.environ["ATTENDANCE_TIMEZONE"] = settings.timezone
            schedule = AttendanceSchedule(
                check_in_time=parse_clock_time(args.check_in_time or settings.check_in_time),
                check_out_time=parse_clock_time(args.check_out_time or settings.check_out_time),
            )
            run_webcam(
                db_path=db_path,
                workbook_path=workbook_path,
                attendance_dir=attendance_dir,
                mode=args.mode,
                schedule=schedule,
                camera_index=args.camera,
                tolerance=args.tolerance,
                process_every=args.process_every,
                scale=args.scale,
                detection_model=args.model,
                cooldown_seconds=args.cooldown,
            )

        elif args.command == "export":
            export_workbook(db_path, workbook_path, attendance_dir)
            print(f"Excel workbook written: {workbook_path}")
            print(f"Daily attendance files written in: {attendance_dir}")

        elif args.command == "employees":
            with database_session(db_path) as conn:
                initialize_database(conn)
                employees = list_employees(conn)
            if not employees:
                print("No employees enrolled yet. Add images, then run: python main.py encode")
            for employee in employees:
                status = "active" if employee["active"] else "inactive"
                print(f"{employee['employee_id']}\t{employee['name']}\t{status}")

        return 0
    except Exception as exc:  # CLI boundary: keep operational errors readable.
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
