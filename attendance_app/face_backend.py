from __future__ import annotations

import importlib
import warnings


def import_face_recognition():
    warnings.filterwarnings("ignore", message="pkg_resources is deprecated.*")
    warnings.filterwarnings("ignore", category=UserWarning, module="face_recognition_models")
    return importlib.import_module("face_recognition")

