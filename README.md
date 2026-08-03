# Company Face Recognition Attendance

This project recognizes employees from a webcam, grants/denies access on screen, updates a local real-time SQLite database, and rewrites an Excel workbook with daily check-in and check-out times.

It follows the same core pattern used by `ageitgey/face_recognition`: create known face encodings from employee images, compare live webcam face encodings to those known faces, then choose the closest match under a tolerance threshold.

## Folder Layout

```text
.
+-- attendance_app/          Python package
+-- data/
|   +-- attendance.db        Local database, generated
+-- attendance/
|   +-- Attendance of 1 August 2026.xlsx
+-- images/                  Add employee face images here
+-- company_settings.json    Company name, time zone, check-in/out times
+-- employees.csv            Employee roster, generated/editable
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

Recommended flow:

```powershell
python main.py roster --force
```

This creates `employees.csv` from the images in `images/`. Review and edit the generated IDs/names before encoding. A plain image name like this:

```text
images/Jane Smith.jpg
```

becomes a roster row like this:

```csv
employee_id,name,image_path,active
EMP001,Jane Smith,Jane Smith.jpg,yes
```

You can also provide IDs directly in image or folder names:

```text
images/EMP001_John_Doe.jpg
images/EMP002_Aisha_Khan.png
images/EMP001_John_Doe/front.jpg
images/EMP001_John_Doe/side.jpg
```

Use a bright, front-facing photo where only that employee's face is visible. The encoder skips images with zero faces or multiple faces.

## Company Settings

Edit `company_settings.json` for each company:

```json
{
  "company_name": "Company",
  "check_in_time": "08:00",
  "check_out_time": "16:00",
  "timezone": ""
}
```

`check_in_time` and `check_out_time` drive auto attendance mode. If the employee is recognized closer to the check-in time, the system records entry/check-in. If recognition is closer to the check-out time, it records exit/check-out. For example, with `08:00` and `16:00`, morning recognitions clock in and afternoon recognitions clock out.

Leave `timezone` blank to use the computer's local time zone, or set an IANA name such as `America/New_York`.

## Initialize And Encode

```powershell
python main.py init-db
python main.py roster --force
python main.py encode
python main.py employees
```

Encoding reads `images/`, stores face encodings in `data/attendance.db`, and creates daily attendance files in `attendance/`.

## Run Attendance

Default single-camera auto mode:

```powershell
python main.py run
```

Auto mode uses the company times in `company_settings.json`.

Dedicated entrance camera:

```powershell
python main.py run --mode entrance
```

Dedicated exit camera:

```powershell
python main.py run --mode exit
```

Auto mode with temporary command-line times:

```powershell
python main.py run --mode auto --check-in-time 8am --check-out-time 4pm
```

Keyboard controls while the camera window is open:

```text
E  switch to entrance/check-in mode
X  switch to exit/check-out mode
R  reload face encodings after adding images
Q  quit
```

The system records one check-in and one check-out per employee per calendar day. Repeated recognitions do not overwrite the first daily check-in or check-out.

## Attendance Excel Files

Daily attendance files are generated in the `attendance/` folder. Each device date gets its own Excel file, named like:

```text
attendance/Attendance of 1 August 2026.xlsx
attendance/Attendance of 2 August 2026.xlsx
```

Each daily file contains:

- `Name of Employee`
- `ID of Employee`
- `Clocked In Time`
- `Clocked Out Time`

The app also keeps `data/attendance.db` as the local database and `data/attendance.xlsx` as a master/admin export, but the daily files in `attendance/` are the files intended for attendance viewing.

You can regenerate the workbook at any time:

```powershell
python main.py export
```

## Useful Options

```powershell
python main.py run --camera 1
python main.py run --check-in-time 07:30 --check-out-time 17:00
python main.py run --tolerance 0.45
python main.py run --process-every 3
python main.py encode --model cnn
```

Lower tolerance is stricter. Start around `0.50`; if employees are falsely matched, lower it toward `0.45`. The `cnn` detector can be more accurate, but it is much slower without a CUDA-capable GPU.

## Time Zone

By default, the app uses the computer's local time zone. To force a business time zone, set `timezone` in `company_settings.json`, pass `--timezone`, or use `ATTENDANCE_TIMEZONE`:

```powershell
$env:ATTENDANCE_TIMEZONE = "America/New_York"
python main.py run
```

Use an IANA time zone name such as `America/New_York`, `America/Chicago`, `America/Denver`, or `America/Los_Angeles`.

## Privacy And Operations

Face images and encodings are biometric data. Keep the `images/` and `data/` folders private, collect employee consent where required, and test thoroughly before connecting this to any physical door hardware.
