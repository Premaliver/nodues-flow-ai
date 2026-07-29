"""Fix frontend templates - app_dept_id and View Documents feature."""
import os

base = r'C:\Users\HP LAPTOP\OneDrive\Desktop\nodues-flow-ai\backend\templates'

departments = ['hostel', 'mess', 'transport', 'scholarship', 'hod']

for dept in departments:
    fp = os.path.join(base, dept, 'dashboard.html')
    with open(fp, 'r') as f:
        content = f.read()
    
    # Fix: app_id -> app_dept_id in onclick
    # Pattern: openXxxModal('${app.application_id}','${app.student_name}')
    import re
    # Match any openXxxModal pattern
    content = re.sub(
        r"(open\w+Modal\()'\$\{app\.application_id\}','\$\{app\.student_name\}'(\))",
        r"\1'${app.app_dept_id}','${app.student_name}','${app.application_id}'\2",
        content
    )
    
    with open(fp, 'w') as f:
        f.write(content)
    print('Updated', dept)

print('Done')
