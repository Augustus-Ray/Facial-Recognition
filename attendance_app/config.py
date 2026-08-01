from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@dataclass(frozen=True)
class AppPaths:
    root: Path
    image_dir: Path
    data_dir: Path
    roster_path: Path
    database_path: Path
    workbook_path: Path


DEFAULT_PATHS = AppPaths(
    root=PROJECT_ROOT,
    image_dir=PROJECT_ROOT / "images",
    data_dir=PROJECT_ROOT / "data",
    roster_path=PROJECT_ROOT / "employees.csv",
    database_path=PROJECT_ROOT / "data" / "attendance.db",
    workbook_path=PROJECT_ROOT / "data" / "attendance.xlsx",
)


def ensure_runtime_dirs(paths: AppPaths = DEFAULT_PATHS) -> None:
    paths.image_dir.mkdir(parents=True, exist_ok=True)
    paths.data_dir.mkdir(parents=True, exist_ok=True)


def now_local() -> datetime:
    timezone_name = os.getenv("ATTENDANCE_TIMEZONE", "").strip()
    if timezone_name:
        try:
            return datetime.now(ZoneInfo(timezone_name))
        except ZoneInfoNotFoundError as exc:
            raise RuntimeError(
                f"Unknown ATTENDANCE_TIMEZONE '{timezone_name}'. Use an IANA name like America/New_York."
            ) from exc
    return datetime.now().astimezone()
