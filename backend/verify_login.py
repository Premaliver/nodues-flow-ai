"""
Verify login credentials using the SAME method as the actual login flow.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import create_app
from models import db
from models.user import User

app = create_app('development')
with app.app_context():
    print("=== VERIFYING LOGIN FLOW (using User.check_password) ===\n")
    
    # Test super admin
    sa = User.query.filter_by(role='super_admin').first()
    if sa:
        print(f"Super Admin: email='{sa.email}'")
        pw_ok = sa.check_password("Prem@2004")
        print(f"  Password 'Prem@2004' matches: {pw_ok}")
        print(f"  Hash type: {sa.password_hash[:20]}...")
    else:
        print("❌ No super admin found!")
    
    print()
    
    # Test all users
    all_users = User.query.all()
    for u in all_users:
        pw = "Prem@2004" if u.role == "super_admin" else "123456"
        ok = u.check_password(pw)
        status = "✅ OK" if ok else "❌ FAIL"
        if not ok:
            print(f"  {u.email} ({u.role}): {status}")
    
    print("\n=== If all OK, login will work! ===")
    print(f"Open: http://127.0.0.1:5000")
    print(f"Role: Super Admin | Username: KPrem | Password: Prem@2004")

