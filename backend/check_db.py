import os, sys
sys.path.insert(0, r'c:\Users\HP LAPTOP\OneDrive\Desktop\nodues-flow-ai\backend')

from app import create_app
from models import db
from models.user import User
from werkzeug.security import check_password_hash

app = create_app('development')
with app.app_context():
    sus = User.query.filter_by(role='super_admin').all()
    print("=== SUPER ADMINS ===")
    print(f"Count: {len(sus)}")
    check_pw = os.environ.get("DEMO_ADMIN_PASSWORD", "Admin@12345")
    for u in sus:
        print(f"  email='{u.email}', status='{u.status}', pw_hash={u.password_hash[:40] if u.password_hash else 'NONE'}...")
        result = check_password_hash(u.password_hash, check_pw)
        print(f"  Password matches check_pw: {result}")
    
    print("\n=== ALL USERS ===")
    all_users = User.query.all()
    print(f"Total: {len(all_users)}")
    for u in all_users:
        print(f"  email='{u.email}', role='{u.role}', status='{u.status}'")
