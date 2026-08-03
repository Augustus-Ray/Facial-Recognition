from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from attendance_app.config import DEFAULT_PATHS


@dataclass(frozen=True)
class CompanySettings:
    company_name: str = "Company"
    check_in_time: str = "08:00"
    check_out_time: str = "16:00"
    timezone: str = ""


def load_company_settings(settings_path: str | Path = DEFAULT_PATHS.settings_path) -> CompanySettings:
    settings_path = Path(settings_path)
    if not settings_path.exists():
        return CompanySettings()

    with settings_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    return CompanySettings(
        company_name=str(data.get("company_name") or "Company").strip() or "Company",
        check_in_time=str(data.get("check_in_time") or "08:00").strip(),
        check_out_time=str(data.get("check_out_time") or "16:00").strip(),
        timezone=str(data.get("timezone") or "").strip(),
    )


def ensure_company_settings(settings_path: str | Path = DEFAULT_PATHS.settings_path) -> Path:
    settings_path = Path(settings_path)
    if settings_path.exists():
        return settings_path

    settings_path.write_text(
        json.dumps(CompanySettings().__dict__, indent=2) + "\n",
        encoding="utf-8",
    )
    return settings_path

