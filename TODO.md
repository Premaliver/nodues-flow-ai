# Fix Progress Tracking

## ✅ Completed
1. ✅ Added Change Password button to all department dashboards (hostel, mess, transport, scholarship, accounts, hod, examination, superadmin)
2. ✅ Added "View Documents" button in hostel process modal (staff can view uploaded docs before approving)
3. ✅ Added `/api/documents/<app_id>` endpoint for staff to fetch application documents
4. ✅ Removed duplicate route in student routes.py
5. ✅ Fixed hostel dashboard modal to properly store app ID and reset docs list

## ✅ Fixes Applied
- Hostel dashboard: Change Password link, View Documents button, proper modal state management
- Student routes: Documents API endpoint, removed duplicate route, cleaned up validation
- All other dashboards: Change Password link added

## ✅ Examination Board Fix
- [x] Fix `dashboard_data` to show applications ready for admit card (query exam ApplicationDepartment pending rows)
- [x] Fix `list_applications` to include student/application details (Approved Apps tab)
- [x] Fix `generate_admit_card` to remove blocking approved check, generate real PDF + QR
- [x] Add `list_admit_cards` endpoint for "Admit Cards Issued" tab
- [x] Add PDF download/view endpoint for admit cards
- [x] Fix frontend dashboard JavaScript for all sidebar sections

## pending (original)
- [x] examination dashboard application not showing
- [x] option on the examination dashboard is not working
- [x] genrating admit card and other option is not working fix it
