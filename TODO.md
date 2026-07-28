# ADVANCED APPLICATION WORKFLOW SYSTEM - TODO

## Phase 1: Database Models (New + Modifications)
- [x] Create Course model with all university courses
- [x] Add academic_department_id to Student model
- [x] Add selected_departments JSON + digital_signature to NoDuesApplication
- [x] Add new document types (application_form, next_sem_fee_receipt)
- [x] Create DigitalSignature model
- [x] Update __init__.py imports
- [x] Create seed_courses.py with all university courses

## Phase 2: Registration Enhancement
- [x] Add department selection (all departments)
- [x] Add course selection (filtered by department)
- [x] Add phone number field
- [x] Update backend auth routes

## Phase 3: Student Application Form (New)
- [x] Create new application form template (apply.html)
- [x] Pre-filled personal info from profile
- [x] Department selection checkboxes
- [x] HOD department selector
- [x] Document upload (exam fee, next sem fee, application form)
- [x] Digital signature pad
- [x] Backend API for form submission

## Phase 4: Backend Routes
- [x] Create student application submission API
- [x] Create document upload API for application form
- [x] Create digital signature save API
- [x] Update accounts routes with sign/stamp feature
- [x] Update hod routes with department filtering
- [x] Update student dashboard to show new flow

## Phase 5: HOD Department Filtering
- [x] HOD sees only students from their academic department
- [x] HOD student listing with full details
- [x] Department-based routing

## Phase 6: Accounts Sign & Stamp
- [x] Verify all department clearances
- [x] Digital sign and stamp
- [x] Forward to HOD

## Phase 7: Examination Admit Card
- [x] Generate admit card after HOD clearance
- [x] QR code integration
- [x] Student admit card download

## Phase 8: Frontend Templates Update
- [x] Register page with all fields
- [x] Student dashboard with new flow
- [x] Accounts dashboard with sign/stamp
- [x] HOD dashboard with department filtering
- [x] Examination dashboard updates

## Phase 9: Testing
- [x] Verify all API endpoints
- [x] Test complete workflow
- [x] Database migration testing
