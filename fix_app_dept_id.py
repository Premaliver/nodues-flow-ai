"""Fix all department routes to include app_dept_id in API responses."""
import os

base = r'C:\Users\HP LAPTOP\OneDrive\Desktop\nodues-flow-ai\backend\blueprints'

files = {
    'hostel': r'\hostel\routes.py',
    'mess': r'\mess\routes.py',
    'transport': r'\transport\routes.py',
    'scholarship': r'\scholarship\routes.py',
    'hod': r'\hod\routes.py',
}

for name, rel_path in files.items():
    filepath = base + rel_path
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Replace the pattern: "application_id": str(app.id),\n                    "application_number"
    old = '"application_id": str(app.id),\n                    "application_number"'
    new = '"application_id": str(app.id),\n                    "app_dept_id": str(app_dept.id),\n                    "application_number"'
    
    # Also handle the hostel format with different indentation
    old2 = '"application_id": str(app.id),\n            "application_number"'
    new2 = '"application_id": str(app.id),\n            "app_dept_id": str(app_dept.id),\n            "application_number"'
    
    content = content.replace(old, new)
    content = content.replace(old2, new2)
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f'✓ Updated {name} routes')

print('\nAll department routes updated with app_dept_id!')
