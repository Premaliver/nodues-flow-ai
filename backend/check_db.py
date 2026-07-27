"""Check database current state."""
import sys
sys.path.insert(0, r'c:\Users\HP LAPTOP\OneDrive\Desktop\nodues-flow-ai\backend')

from app import create_app, bcrypt
from models import db
from models.user import User

app = create_app('development')
with app.app_context():
    # Check super admin
    print("=== SUPER ADMINS ===")
    sus = User.query.filter_by(role='super_admin').all()
    print(f"Count: {len(sus)}")
    for u in sus:
        print(f"  email='{u.email}', status='{u.status}', pw_hash={u.password_hash[:40] if u.password_hash else 'NONE'}...")
        # Test password
        result = bcrypt.check_password_hash(u.password_hash, "Prem@2004")
        print(f"  Password 'Prem@2004' matches: {result}")
    
    print("\n=== ALL USERS ===")
    all_users = User.query.all()
    print(f"Total: {len(all_users)}")
    for u in all_users:
        print(f"  email='{u.email}', role='{u.role}', status='{u.status}'")

