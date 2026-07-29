# Student Dashboard & Registration Updates — DONE ✅

## Step 1: Registration form — Add father name & phone fields ✅
- File: `backend/templates/auth/register.html`
  - Added "Father's Name" input field
  - Added "Father's Phone No" input field
  - Included in JSON submission payload

## Step 2: Auth route — Save father fields to Student model ✅
- File: `backend/blueprints/auth/routes.py`
  - Extracts `father_name` and `father_phone` from request data
  - Passes to Student constructor as `father_name` and `guardian_phone`

## Step 3: Student model — Expose guardian_phone in API ✅
- File: `backend/models/student.py`
  - Added `guardian_phone` to `to_dict()` output

## Step 4: Apply page — Auto-detect HOD from registration data ✅
- File: `backend/templates/student/apply.html`
  - Removed "Select Your HOD Department" dropdown
  - Added read-only auto-detected HOD field based on course_name
  - Updated review and submission logic

## Step 5: Student routes — Use auto-detected HOD ✅
- File: `backend/blueprints/student/routes.py`
  - Backend already auto-finds HOD via `Department.query.filter_by(role="hod")`
  - Removed manual `hod_department` from `@validate_json` and frontend validation

## Step 6: Dashboard — Show father name & phone ✅
- File: `backend/templates/student/dashboard.html`
  - Display father name and guardian phone in student info line

