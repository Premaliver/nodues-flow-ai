"""Fix frontend templates - use utf-8 encoding."""
import os, re, glob

base = r'C:\Users\HP LAPTOP\OneDrive\Desktop\nodues-flow-ai\backend\templates'

for dept in ['hostel', 'mess', 'transport', 'scholarship', 'hod']:
    fp = os.path.join(base, dept, 'dashboard.html')
    with open(fp, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix openXxxModal to use app_dept_id and pass application_id
    content = re.sub(
        r"(open\w+Modal\()'\$\{app\.application_id\}','\$\{app\.student_name\}'(\))",
        r"\1'${app.app_dept_id}','${app.student_name}','${app.application_id}'\2",
        content
    )
    
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Updated {dept}')

print('All frontend templates fixed!')
