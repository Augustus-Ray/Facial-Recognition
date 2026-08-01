from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from attendance_app.config import DEFAULT_PATHS, SUPPORTED_IMAGE_EXTENSIONS


ROSTER_HEADERS = ["employee_id", "name", "image_path", "active"]
FILENAME_ID_PATTERN = re.compile(
    r"^(?P<employee_id>[A-Za-z0-9][A-Za-z0-9-]*)(?:\s*_\s*|\s+-\s+)(?P<name>.+)$"
)
ACTIVE_VALUES = {"", "1", "active", "true", "yes", "y"}


@dataclass(frozen=True)
class RosterEntry:
    employee_id: str
    name: str
    image_path: Path
    source_image: str
    active: bool = True


def iter_image_files(image_dir: str | Path) -> list[Path]:
    image_dir = Path(image_dir)
    return sorted(
        path
        for path in image_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
    )


def read_roster(
    roster_path: str | Path = DEFAULT_PATHS.roster_path,
    image_dir: str | Path = DEFAULT_PATHS.image_dir,
) -> list[RosterEntry]:
    roster_path = Path(roster_path)
    image_dir = Path(image_dir)
    if not roster_path.exists():
        return []

    entries: list[RosterEntry] = []
    with roster_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"Roster is empty: {roster_path}")

        normalized_headers = {header.strip().lower() for header in reader.fieldnames if header}
        missing = {"employee_id", "name", "image_path"} - normalized_headers
        if missing:
            raise ValueError(f"Roster is missing required column(s): {', '.join(sorted(missing))}")

        for line_number, row in enumerate(reader, start=2):
            normalized = {
                (key or "").strip().lower(): (value or "").strip()
                for key, value in row.items()
            }
            employee_id = normalized.get("employee_id", "").upper()
            name = " ".join(normalized.get("name", "").split())
            source_image = normalized.get("image_path", "").replace("\\", "/")
            active = normalized.get("active", "yes").strip().lower() in ACTIVE_VALUES

            if not employee_id or not name or not source_image:
                raise ValueError(
                    f"Roster row {line_number} must include employee_id, name, and image_path."
                )
            entries.append(
                RosterEntry(
                    employee_id=employee_id,
                    name=name,
                    image_path=image_dir / source_image,
                    source_image=source_image,
                    active=active,
                )
            )
    return entries


def generate_roster(
    *,
    image_dir: str | Path = DEFAULT_PATHS.image_dir,
    roster_path: str | Path = DEFAULT_PATHS.roster_path,
    employee_prefix: str = "EMP",
    start_number: int = 1,
    overwrite: bool = False,
) -> int:
    image_dir = Path(image_dir)
    roster_path = Path(roster_path)
    image_dir.mkdir(parents=True, exist_ok=True)
    roster_path.parent.mkdir(parents=True, exist_ok=True)

    if roster_path.exists() and not overwrite:
        raise FileExistsError(f"Roster already exists: {roster_path}. Use --force to overwrite it.")

    grouped: dict[str, list[Path]] = {}
    for image_path in iter_image_files(image_dir):
        token = image_path.relative_to(image_dir).parts[0] if image_path.parent != image_dir else image_path.stem
        grouped.setdefault(token, []).append(image_path)

    rows: list[dict[str, str]] = []
    for index, token in enumerate(sorted(grouped), start=start_number):
        fallback_employee_id = f"{employee_prefix}{index:03d}"
        employee_id, name = identity_from_token(token, fallback_employee_id)
        for image_path in grouped[token]:
            rows.append(
                {
                    "employee_id": employee_id,
                    "name": name,
                    "image_path": image_path.relative_to(image_dir).as_posix(),
                    "active": "yes",
                }
            )

    with roster_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROSTER_HEADERS)
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)


def identity_from_token(token: str, fallback_employee_id: str | None = None) -> tuple[str, str]:
    token = token.strip()
    match = FILENAME_ID_PATTERN.match(token)
    if match:
        return match.group("employee_id").strip().upper(), clean_name(match.group("name"))

    if fallback_employee_id:
        return fallback_employee_id.strip().upper(), clean_name(token)

    raise ValueError(
        f"Cannot read employee ID/name from '{token}'. Use employees.csv, "
        "or use image/folder names like EMP001_John_Doe."
    )


def entries_from_filenames(image_dir: str | Path) -> list[RosterEntry]:
    image_dir = Path(image_dir)
    entries: list[RosterEntry] = []
    for image_path in iter_image_files(image_dir):
        token = image_path.relative_to(image_dir).parts[0] if image_path.parent != image_dir else image_path.stem
        employee_id, name = identity_from_token(token)
        entries.append(
            RosterEntry(
                employee_id=employee_id,
                name=name,
                image_path=image_path,
                source_image=image_path.relative_to(image_dir).as_posix(),
            )
        )
    return entries


def clean_name(value: str) -> str:
    name = value.replace("_", " ").strip()
    return " ".join(name.split())
