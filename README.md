# Company Face Recognition Attendance

This project recognizes employees from a webcam, grants/denies access on screen, updates a local real-time SQLite database, and rewrites an Excel workbook with daily check-in and check-out times.

It follows the same core pattern used by `ageitgey/face_recognition`: create known face encodings from employee images, compare live webcam face encodings to those known faces, then choose the closest match under a tolerance threshold.

## Folder Layout

```text
.
+-- attendance_app/          Python package
+-- data/
|   +-- attendance.db        Local database, generated
|   +-- attendance.xlsx      Excel attendance file, generated
+-- images/                  Add employee face images here
+-- main.py                  Command-line app
+-- requirements.txt
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python check_environment.py
```

`face_recognition` depends on `dlib`. On Windows, install problems are usually related to C++ build tools, CMake, or Python/dlib wheel compatibility.

If `python` or `pip` opens the Microsoft Store or says the file cannot be accessed, install Python from python.org and check "Add python.exe to PATH", or disable the Windows App Execution Aliases for Python in Windows Settings. Then reopen PowerShell and create the `.venv` again.

## Add Employee Images

Employee IDs are the unique value. Put one clear face per image.

Flat file style:

```text
images/EMP001_John_Doe.jpg
images/EMP002_Aisha_Khan.png
```

Multiple images per employee:

```text
images/EMP001_John_Doe/front.jpg
images/EMP001_John_Doe/side.jpg
images/EMP002_Aisha_Khan/photo1.jpg
```

Use a bright, front-facing photo where only that employee's face is visible. The encoder skips images with zero faces or multiple faces.

## Initialize And Encode

```powershell
python main.py init-db
python main.py encode
python main.py employees
```

Encoding reads `images/`, stores face encodings in `data/attendance.db`, and writes `data/attendance.xlsx`.

## Run Attendance

Entrance camera/check-in:

```powershell
python main.py run --mode entrance
```

Exit camera/check-out:

```powershell
python main.py run --mode exit
```

Keyboard controls while the camera window is open:

```text
E  switch to entrance/check-in mode
X  switch to exit/check-out mode
R  reload face encodings after adding images
Q  quit
```

The system records one check-in and one check-out per employee per calendar day. Repeated recognitions do not overwrite the first daily check-in or check-out.

## Excel Output

The workbook `data/attendance.xlsx` contains:

- `Employees`: employee IDs, names, and encoding counts.
- `Daily Attendance`: date, employee ID, name, check-in time, and check-out time.
- `Access Events`: recent recognition attempts, including unknown faces.

You can regenerate the workbook at any time:

```powershell
python main.py export
```

## Useful Options

```powershell
python main.py run --camera 1
python main.py run --tolerance 0.45
python main.py run --process-every 3
python main.py encode --model cnn
```

Lower tolerance is stricter. Start around `0.50`; if employees are falsely matched, lower it toward `0.45`. The `cnn` detector can be more accurate, but it is much slower without a CUDA-capable GPU.

## Time Zone

By default, the app uses the computer's local time zone. To force a business time zone:

```powershell
$env:ATTENDANCE_TIMEZONE = "America/New_York"
python main.py run --mode entrance
```

Use an IANA time zone name such as `America/New_York`, `America/Chicago`, `America/Denver`, or `America/Los_Angeles`.

## Privacy And Operations

Face images and encodings are biometric data. Keep the `images/` and `data/` folders private, collect employee consent where required, and test thoroughly before connecting this to any physical door hardware.
