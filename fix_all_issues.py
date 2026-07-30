"""
Fix all remaining issues:
1. Accounts routes - add app_dept_id to API response
2. Accounts dashboard - use app_dept_id in process calls
3. Student routes - handle network errors better
4. Superadmin seed issue - add check for existing default users
"""
import re

# 1. Fix accounts routes - add app_dept_id
with open('backend/blueprints/accounts/routes.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    """    pending_list = []
    for app_dept, app, student, user in pending_apps:
        pending_list.append({
            "application_id": str(app.id),
            "application_number": app.application_number,
            "student_name": user.full_name,
            "roll_number": student.roll_number,
            "course_name": student.course_name,
            "semester": student.current_semester,
            "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
            "category": student.category,
        })""",
    """    pending_list = []
    for app_dept, app, student, user in pending_apps:
        pending_list.append({
            "app_dept_id": str(app_dept.id),
            "application_id": str(app.id),
            "application_number": app.application_number,
            "student_name": user.full_name,
            "roll_number": student.roll_number,
            "course_name": student.course_name,
            "semester": student.current_semester,
            "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
            "category": student.category,
        })"""
)

with open('backend/blueprints/accounts/routes.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('✓ Fixed accounts routes - added app_dept_id')

# 2. Fix accounts dashboard template - use app_dept_id
with open('backend/templates/accounts/dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the openModal call to use app_dept_id
content = content.replace(
    "openModal('${app.application_id}', '${app.student_name}', '${app.application_number}')",
    "openModal('${app.app_dept_id}', '${app.student_name}', '${app.application_number}')"
)

with open('backend/templates/accounts/dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)
print('✓ Fixed accounts dashboard - using app_dept_id in process')

# 3. Fix superadmin seed - make it check if default users exist by email to prevent re-creation
with open('backend/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the auto-seed to check by email instead of just any user
old_seed_check = """    # Only seed if no users exist
    if User.query.first():
        return"""

new_seed_check = """    # Only seed if NO DEFAULT users exist (check by known emails)
    default_emails = ["kprem@rayatbahra.edu", "accounts@rayatbahra.edu", "hostel@rayatbahra.edu", 
                      "mess@rayatbahra.edu", "transport@rayatbahra.edu", "scholarship@rayatbahra.edu", 
                      "hod.cse@rayatbahra.edu", "examination@rayatbahra.edu", "student@rayatbahra.edu"]
    existing_default = User.query.filter(User.email.in_(default_emails)).first()
    if existing_default:
        return"""

content = content.replace(old_seed_check, new_seed_check)

with open('backend/app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('✓ Fixed auto-seed - checks by email to avoid re-creating deleted users')

# 4. Fix student apply - better error handling for network issue
with open('backend/templates/student/apply.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Improve error message to show actual error
content = content.replace(
    """            } catch(e) {
                showError('Network error. Please try again.');
                btn.disabled = false;
                btn.innerHTML = '📤 Submit Application';
                console.error(e);
            }""",
    """            } catch(e) {
                console.error('Submission error:', e);
                showError('Error: ' + (e.message || 'Network error. Please try again.'));
                btn.disabled = false;
                btn.innerHTML = '📤 Submit Application';
            }"""
)

with open('backend/templates/student/apply.html', 'w', encoding='utf-8') as f:
    f.write(content)
print('✓ Fixed student apply - better error display')

# 5. Fix scholarship route to also include app_dept_id
with open('backend/blueprints/scholarship/routes.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    """        "pending_applications": [
                {
                    "application_id": str(app.id),
                    "application_number": app.application_number,""",
    """        "pending_applications": [
                {
                    "app_dept_id": str(app_dept.id),
                    "application_id": str(app.id),
                    "application_number": app.application_number,"""
)

with open('backend/blueprints/scholarship/routes.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('✓ Fixed scholarship routes - added app_dept_id')

# 6. Fix HOD routes to also include app_dept_id
with open('backend/blueprints/hod/routes.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    """                {
                    "application_id": str(app.id),
                    "application_number": app.application_number,""",
    """                {
                    "app_dept_id": str(app_dept.id),
                    "application_id": str(app.id),
                    "application_number": app.application_number,"""
)

with open('backend/blueprints/hod/routes.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('✓ Fixed HOD routes - added app_dept_id')

# 7. Fix transport routes to include app_dept_id
with open('backend/blueprints/transport/routes.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Check if transport already has app_dept_id
if 'app_dept_id' not in content:
    content = content.replace(
        """                {
                    "application_id": str(app.id),
                    "application_number": app.application_number,""",
        """                {
                    "app_dept_id": str(app_dept.id),
                    "application_id": str(app.id),
                    "application_number": app.application_number,"""
    )
    with open('backend/blueprints/transport/routes.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('✓ Fixed transport routes - added app_dept_id')
else:
    print('✓ Transport routes already have app_dept_id')

# 8. Fix mess routes to include app_dept_id
with open('backend/blueprints/mess/routes.py', 'r', encoding='utf-8') as f:
    content = f.read()

if 'app_dept_id' not in content:
    content = content.replace(
        """                {
                    "application_id": str(app.id),
                    "application_number": app.application_number,""",
        """                {
                    "app_dept_id": str(app_dept.id),
                    "application_id": str(app.id),
                    "application_number": app.application_number,"""
    )
    with open('backend/blueprints/mess/routes.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('✓ Fixed mess routes - added app_dept_id')
else:
    print('✓ Mess routes already have app_dept_id')

# 9. Fix hostel routes to include app_dept_id
with open('backend/blueprints/hostel/routes.py', 'r', encoding='utf-8') as f:
    content = f.read()

if 'app_dept_id' not in content:
    content = content.replace(
        """                {
                    "application_id": str(app.id),
                    "application_number": app.application_number,""",
        """                {
                    "app_dept_id": str(app_dept.id),
                    "application_id": str(app.id),
                    "application_number": app.application_number,"""
    )
    with open('backend/blueprints/hostel/routes.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('✓ Fixed hostel routes - added app_dept_id')
else:
    print('✓ Hostel routes already have app_dept_id')

# 10. Fix examination routes to include app_dept_id
with open('backend/blueprints/examination/routes.py', 'r', encoding='utf-8') as f:
    content = f.read()

if 'app_dept_id' not in content:
    content = content.replace(
        """                {
                    "application_id": str(app.id),
                    "application_number": app.application_number,""",
        """                {
                    "app_dept_id": str(app_dept.id),
                    "application_id": str(app.id),
                    "application_number": app.application_number,"""
    )
    with open('backend/blueprints/examination/routes.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('✓ Fixed examination routes - added app_dept_id')
else:
    print('✓ Examination routes already have app_dept_id')

print('\n✅ All fixes applied!')
