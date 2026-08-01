from __future__ import annotations

import importlib
from importlib import metadata
import platform
import sys
import warnings


REQUIRED_MODULES = {
    "cv2": "opencv-python",
    "face_recognition": "face-recognition",
    "numpy": "numpy",
    "openpyxl": "openpyxl",
}


def main() -> int:
    print(f"Python: {sys.version.split()[0]}")
    print(f"Executable: {sys.executable}")
    print(f"Platform: {platform.platform()}")
    print()

    missing: list[str] = []
    warnings.filterwarnings("ignore", message="pkg_resources is deprecated.*")
    for module_name, package_name in REQUIRED_MODULES.items():
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            print(f"[missing] {module_name}: {exc}")
            missing.append(module_name)
            continue

        try:
            version = metadata.version(package_name)
        except metadata.PackageNotFoundError:
            version = getattr(module, "__version__", "installed")
        print(f"[ok]      {module_name}: {version}")

    if missing:
        print()
        print("Install missing packages with:")
        print("python -m pip install -r requirements.txt")
        return 1

    print()
    print("Environment ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
