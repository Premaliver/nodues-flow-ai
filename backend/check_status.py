import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db
from models.user import User
from models.department import Department

app = create_app("development")
with app.app_context():
    users = User.query.count()
    depts = Department.query.count()
    sa = User.query.filter_by(role="super_admin").first()
    print(f"Users: {users}")
    print(f"Depts: {depts}")
    if sa:
        print(f"Super admin: {sa.email} / {sa.first_name} {sa.last_name}")
        print(f"PW check (Prem@2004): {sa.check_password('Prem@2004')}")
        print(f"Status: {sa.status}")
        print(f"Is active: {sa.is_active_user}")
    else:
        print("ERROR: No super_admin found!")

