# Company Face Recognition Attendance

This app uses a webcam to recognize enrolled employees and record their attendance. When a known employee is seen, the app saves a check-in or check-out time in a local SQLite database and updates the Excel attendance files.

This is a local attendance prototype. It displays access messages on screen but does not control a real door lock.

## Quick Start

Open PowerShell in this project folder.

For a new installation, create the Python environment and install the dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python check_environment.py
```

If `.venv` already exists, activate it and check the environment:

```powershell
.\.venv\Scripts\activate
python check_environment.py
```

Prepare the database and employee faces:

```powershell
python main.py init-db
python main.py roster --force
python main.py encode
python main.py employees
```

Start attendance recognition:

```powershell
python main.py run
```

Press `Q` in the camera window to quit.

## What the Setup Commands Do

`python main.py init-db`

Creates the local database and attendance folders if they do not already exist.

`python main.py roster --force`

Reads the employee photos in `images/` and creates `employees.csv`.

`python main.py encode`

Converts each valid employee photo into numeric face data and stores it in `data/attendance.db`.

`python main.py employees`

Lists the employees currently stored in the database.

`python main.py run`

Opens the webcam and starts marking attendance.

## Add Employees

Place employee photos in the `images/` folder. Use a clear, front-facing photo containing only that employee's face. Images with no face or more than one face are skipped during encoding.

Supported image types are `.jpg`, `.jpeg`, `.png`, `.bmp`, and `.webp`.

A simple filename works:

```text
images/Jane Smith.jpg
```

After running `python main.py roster --force`, it produces a row like this:

```csv
employee_id,name,image_path,active
EMP001,Jane Smith,Jane Smith.jpg,yes
```

You can also include the employee ID in the filename:

```text
images/EMP001_John_Doe.jpg
images/EMP002_Aisha_Khan.png
```

After adding or changing photos, rebuild the roster and face encodings:

```powershell
python main.py roster --force
python main.py encode
python main.py employees
```

Review `employees.csv` before encoding if you need to correct an ID, name, image path, or active status.

## Mark Attendance

Start the app in automatic mode:

```powershell
python main.py run
```

Automatic mode compares the current time with the configured check-in and check-out times. With the default settings of `08:00` and `16:00`, scans nearer the morning time are treated as check-ins and scans nearer the afternoon time are treated as check-outs.

You can force a specific mode:

```powershell
python main.py run --mode entrance
python main.py run --mode exit
```

Keyboard controls in the camera window:

```text
E  switch to entrance/check-in mode
X  switch to exit/check-out mode
R  reload stored face encodings
Q  quit
```

The app stores only the first check-in and first check-out for each employee on a given day. Repeated scans do not replace those times.

## Attendance Files

The main database is:

```text
data/attendance.db
```

The master Excel workbook is:

```text
data/attendance.xlsx
```

Daily attendance files are stored in `attendance/` and named by date:

```text
attendance/Attendance of 1 August 2026.xlsx
attendance/Attendance of 2 August 2026.xlsx
```

Each daily file contains the employee name, employee ID, clock-in time, and clock-out time.

Regenerate the Excel files from the database with:

```powershell
python main.py export
```

## Company Settings

Edit `company_settings.json` to change the company name, attendance times, or time zone:

```json
{
  company_name: Company,
  check_in_time: 08:00,
  check_out_time: 16:00,
  timezone: "
}
```

Leave `timezone` blank to use the computer's local time zone. To force a specific time zone, use an IANA time zone name such as `America/New_York`.

Temporary times can also be supplied when starting the app:

```powershell
python main.py run --check-in-time 07:30 --check-out-time 17:00
```

## Useful Options

Use another camera:

```powershell
python main.py run --camera 1
```

Make face matching stricter:

```powershell
python main.py run --tolerance 0.45
```

The default tolerance is `0.50`. A lower value is stricter. This may reduce false matches, but it can also reject genuine employees more often.

Process fewer frames to reduce computer usage:

```powershell
python main.py run --process-every 3
```

Use the CNN face detector while encoding:

```powershell
python main.py encode --model cnn
```

The CNN detector is considerably slower on computers without a compatible GPU.

## Troubleshooting

Check for missing dependencies:

```powershell
python check_environment.py
pip install -r requirements.txt
```

If `python` or `pip` opens the Microsoft Store, install Python from python.org and enable the Add Python to PATH option. You may also need to disable the Python App Execution Aliases in Windows Settings.

If `face_recognition` or `dlib` fails to install on Windows, check the Python version, CMake, C++ build tools, and dlib wheel compatibility.

If no employees are enrolled, run:

```powershell
python main.py roster --force
python main.py encode
python main.py employees
```

If the webcam does not open, try another camera number:

```powershell
python main.py run --camera 1
```

## Folder Guide

```text
.
+-- attendance_app/          Application source code
+-- attendance/              Daily Excel attendance files
+-- data/                    Database and master Excel workbook
+-- images/                  Employee face photos
+-- tests/                   Automated tests
+-- company_settings.json    Company times and time zone
+-- employees.csv            Employee roster
+-- main.py                  Command-line application
+-- requirements.txt         Python dependencies
```

## Privacy and Limitations

Employee photos and face encodings are biometric data. Keep the `images/` and `data/` folders private and do not include them in a public repository or unprotected project archive.

Before workplace use, inform employees, meet the applicable consent and legal requirements, define a retention period, and provide a suitable alternative attendance method where required.

This prototype does not include liveness detection, database encryption, administrator login, automatic backups, formal accuracy testing, or demographic fairness testing.
