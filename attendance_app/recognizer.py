from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from attendance_app.config import now_local
from attendance_app.database import database_session, fetch_known_faces, initialize_database, log_unknown_face, record_attendance
from attendance_app.excel_exporter import export_workbook
from attendance_app.face_backend import import_face_recognition
from attendance_app.schedule import AttendanceSchedule, describe_schedule, resolve_attendance_mode


@dataclass(frozen=True)
class KnownFace:
    employee_id: str
    name: str
    source_image: str
    encoding: object


@dataclass(frozen=True)
class Detection:
    top: int
    right: int
    bottom: int
    left: int
    employee_id: str | None
    name: str
    distance: float | None
    message: str
    access_granted: bool


def run_webcam(
    *,
    db_path: str | Path,
    workbook_path: str | Path,
    attendance_dir: str | Path,
    schedule: AttendanceSchedule,
    mode: str = "auto",
    camera_index: int = 0,
    tolerance: float = 0.50,
    process_every: int = 2,
    scale: float = 0.25,
    detection_model: str = "hog",
    cooldown_seconds: int = 20,
) -> None:
    try:
        import cv2
        face_recognition = import_face_recognition()
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("OpenCV, numpy, and face_recognition are required. Run: pip install -r requirements.txt") from exc

    if process_every < 1:
        raise ValueError("--process-every must be at least 1")
    if not 0 < scale <= 1:
        raise ValueError("--scale must be greater than 0 and no larger than 1")

    with database_session(db_path) as conn:
        initialize_database(conn)
        known_faces = _load_known_faces(conn, np)

    if not known_faces:
        raise RuntimeError("No face encodings found. Add employee images, then run: python main.py encode")

    known_encodings = [face.encoding for face in known_faces]
    video_capture = cv2.VideoCapture(camera_index)
    if not video_capture.isOpened():
        raise RuntimeError(f"Could not open camera index {camera_index}.")

    current_mode = mode
    frame_number = 0
    detections: list[Detection] = []
    last_logged: dict[tuple[str, str], datetime] = {}
    last_unknown_log: datetime | None = None
    status_line = "Ready"

    try:
        while True:
            ok, frame = video_capture.read()
            if not ok:
                raise RuntimeError("Could not read from the webcam.")

            if frame_number % process_every == 0:
                detections, status_line, last_unknown_log = _process_frame(
                    frame=frame,
                    current_mode=current_mode,
                    schedule=schedule,
                    known_faces=known_faces,
                    known_encodings=known_encodings,
                    tolerance=tolerance,
                    scale=scale,
                    detection_model=detection_model,
                    camera_index=camera_index,
                    db_path=db_path,
                    workbook_path=workbook_path,
                    attendance_dir=attendance_dir,
                    last_logged=last_logged,
                    last_unknown_log=last_unknown_log,
                    cooldown_seconds=cooldown_seconds,
                    cv2=cv2,
                    face_recognition=face_recognition,
                    np=np,
                )

            _draw_overlay(frame, detections, current_mode, schedule, status_line, len(known_faces), tolerance, cv2)
            cv2.imshow("Company Attendance - Face Recognition", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("e"):
                current_mode = "entrance"
                status_line = "Mode switched to entrance"
            elif key == ord("x"):
                current_mode = "exit"
                status_line = "Mode switched to exit"
            elif key == ord("r"):
                with database_session(db_path) as conn:
                    initialize_database(conn)
                    known_faces = _load_known_faces(conn, np)
                known_encodings = [face.encoding for face in known_faces]
                status_line = f"Reloaded {len(known_faces)} known face encoding(s)"

            frame_number += 1
    finally:
        video_capture.release()
        cv2.destroyAllWindows()


def _process_frame(
    *,
    frame,
    current_mode: str,
    schedule: AttendanceSchedule,
    known_faces: list[KnownFace],
    known_encodings: list,
    tolerance: float,
    scale: float,
    detection_model: str,
    camera_index: int,
    db_path: str | Path,
    workbook_path: str | Path,
    attendance_dir: str | Path,
    last_logged: dict[tuple[str, str], datetime],
    last_unknown_log: datetime | None,
    cooldown_seconds: int,
    cv2,
    face_recognition,
    np,
) -> tuple[list[Detection], str, datetime | None]:
    small_frame = cv2.resize(frame, (0, 0), fx=scale, fy=scale)
    rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
    face_locations = face_recognition.face_locations(rgb_small_frame, model=detection_model)
    face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

    detections: list[Detection] = []
    status_line = "No face detected"

    for location, face_encoding in zip(face_locations, face_encodings):
        top, right, bottom, left = _scale_location(location, scale)
        match, distance = _best_match(face_encoding, known_faces, known_encodings, tolerance, np)
        event_time = now_local()
        resolved_mode = resolve_attendance_mode(current_mode, event_time, schedule)

        if match is None:
            message = "ACCESS DENIED - UNKNOWN"
            if last_unknown_log is None or event_time - last_unknown_log >= timedelta(seconds=cooldown_seconds):
                with database_session(db_path) as conn:
                    initialize_database(conn)
                    log_unknown_face(
                        conn,
                        mode=resolved_mode,
                        message=message,
                        event_time=event_time,
                        camera_index=camera_index,
                        distance=distance,
                    )
                export_workbook(db_path, workbook_path, attendance_dir)
                last_unknown_log = event_time
            detections.append(
                Detection(top, right, bottom, left, None, "Unknown", distance, message, False)
            )
            status_line = message
            continue

        cooldown_key = (match.employee_id, resolved_mode)
        last_event_time = last_logged.get(cooldown_key)
        if last_event_time and event_time - last_event_time < timedelta(seconds=cooldown_seconds):
            message = f"RECOGNIZED - {match.name}"
            detections.append(
                Detection(top, right, bottom, left, match.employee_id, match.name, distance, message, True)
            )
            status_line = message
            continue

        with database_session(db_path) as conn:
            initialize_database(conn)
            result = record_attendance(
                conn,
                employee_id=match.employee_id,
                name=match.name,
                mode=resolved_mode,
                event_time=event_time,
                camera_index=camera_index,
                distance=distance,
            )
        export_workbook(db_path, workbook_path, attendance_dir)
        last_logged[cooldown_key] = event_time
        detections.append(
            Detection(
                top,
                right,
                bottom,
                left,
                match.employee_id,
                match.name,
                distance,
                result.message,
                result.access_granted,
            )
        )
        status_line = result.message

    return detections, status_line, last_unknown_log


def _load_known_faces(conn, np) -> list[KnownFace]:
    return [
        KnownFace(
            employee_id=row["employee_id"],
            name=row["name"],
            source_image=row["source_image"],
            encoding=np.array(row["encoding"]),
        )
        for row in fetch_known_faces(conn)
    ]


def _best_match(face_encoding, known_faces: list[KnownFace], known_encodings: list, tolerance: float, np):
    distances = np.array([])
    if known_encodings:
        face_recognition = import_face_recognition()

        distances = face_recognition.face_distance(known_encodings, face_encoding)
    if len(distances) == 0:
        return None, None
    best_index = int(np.argmin(distances))
    distance = float(distances[best_index])
    if distance <= tolerance:
        return known_faces[best_index], distance
    return None, distance


def _scale_location(location: tuple[int, int, int, int], scale: float) -> tuple[int, int, int, int]:
    top, right, bottom, left = location
    factor = 1 / scale
    return int(top * factor), int(right * factor), int(bottom * factor), int(left * factor)


def _draw_overlay(
    frame,
    detections: list[Detection],
    mode: str,
    schedule: AttendanceSchedule,
    status: str,
    known_count: int,
    tolerance: float,
    cv2,
) -> None:
    height, width = frame.shape[:2]
    cv2.rectangle(frame, (0, 0), (width, 76), (20, 20, 20), cv2.FILLED)
    cv2.putText(
        frame,
        f"Mode: {_mode_label(mode, schedule)} | Known encodings: {known_count} | Tolerance: {tolerance:.2f}",
        (16, 28),
        cv2.FONT_HERSHEY_DUPLEX,
        0.62,
        (255, 255, 255),
        1,
    )
    cv2.putText(
        frame,
        "Keys: E entrance | X exit | R reload faces | Q quit",
        (16, 58),
        cv2.FONT_HERSHEY_DUPLEX,
        0.52,
        (210, 210, 210),
        1,
    )
    cv2.putText(
        frame,
        _fit_text(status, 54),
        (16, height - 18),
        cv2.FONT_HERSHEY_DUPLEX,
        0.62,
        (255, 255, 255),
        1,
    )

    for detection in detections:
        color = (48, 180, 83) if detection.access_granted else (50, 50, 220)
        cv2.rectangle(frame, (detection.left, detection.top), (detection.right, detection.bottom), color, 2)

        label_top = max(detection.top - 64, 78)
        cv2.rectangle(frame, (detection.left, label_top), (detection.right, detection.top), color, cv2.FILLED)
        identity = detection.name
        if detection.employee_id:
            identity = f"{detection.employee_id} {detection.name}"
        if detection.distance is not None:
            identity = f"{identity} ({detection.distance:.2f})"
        cv2.putText(
            frame,
            _fit_text(identity, 32),
            (detection.left + 6, label_top + 24),
            cv2.FONT_HERSHEY_DUPLEX,
            0.55,
            (255, 255, 255),
            1,
        )
        cv2.putText(
            frame,
            _fit_text(detection.message, 34),
            (detection.left + 6, label_top + 50),
            cv2.FONT_HERSHEY_DUPLEX,
            0.45,
            (255, 255, 255),
            1,
        )


def _fit_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def _mode_label(mode: str, schedule: AttendanceSchedule) -> str:
    if mode == "auto":
        return f"AUTO ({describe_schedule(schedule)})"
    return mode.upper()
