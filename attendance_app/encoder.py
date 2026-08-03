from __future__ import annotations

from pathlib import Path

from attendance_app.config import DEFAULT_PATHS, ensure_runtime_dirs
from attendance_app.database import EncodingRecord, database_session, initialize_database, replace_face_encodings
from attendance_app.excel_exporter import export_workbook
from attendance_app.face_backend import import_face_recognition
from attendance_app.roster import entries_from_filenames, read_roster


def generate_encodings(
    *,
    image_dir: str | Path = DEFAULT_PATHS.image_dir,
    roster_path: str | Path = DEFAULT_PATHS.roster_path,
    db_path: str | Path = DEFAULT_PATHS.database_path,
    workbook_path: str | Path | None = DEFAULT_PATHS.workbook_path,
    attendance_dir: str | Path = DEFAULT_PATHS.attendance_dir,
    detection_model: str = "hog",
) -> int:
    try:
        face_recognition = import_face_recognition()
    except ImportError as exc:
        raise RuntimeError("face_recognition is required. Run: pip install -r requirements.txt") from exc

    image_dir = Path(image_dir)
    roster_path = Path(roster_path)
    ensure_runtime_dirs()
    if not image_dir.exists():
        raise FileNotFoundError(f"Image folder does not exist: {image_dir}")

    records: list[EncodingRecord] = []
    warnings: list[str] = []
    roster_entries = read_roster(roster_path, image_dir)
    if not roster_entries:
        roster_entries = entries_from_filenames(image_dir)

    for entry in roster_entries:
        if not entry.active:
            continue
        image_path = entry.image_path
        if not image_path.exists():
            warnings.append(f"Skipped {entry.source_image}: file does not exist.")
            continue
        image = face_recognition.load_image_file(str(image_path))
        face_locations = face_recognition.face_locations(image, model=detection_model)
        encodings = face_recognition.face_encodings(image, face_locations)

        if len(encodings) != 1:
            warnings.append(
                f"Skipped {image_path}: expected exactly 1 face, found {len(encodings)}."
            )
            continue

        records.append(
            EncodingRecord(
                employee_id=entry.employee_id,
                name=entry.name,
                source_image=entry.source_image,
                encoding=encodings[0],
            )
        )

    if not records:
        detail = "\n".join(warnings)
        hint = (
            "No usable employee images were found. Use names like "
            "images/EMP001_John_Doe.jpg, or create employees.csv with employee_id,name,image_path."
        )
        raise RuntimeError(f"{hint}\n{detail}".strip())

    with database_session(db_path) as conn:
        initialize_database(conn)
        count = replace_face_encodings(conn, records)

    if workbook_path:
        export_workbook(db_path, workbook_path, attendance_dir)

    for warning in warnings:
        print(f"Warning: {warning}")

    return count
