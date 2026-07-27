"""
Fix super admin credentials in the database.
The init_db.py was using flask_bcrypt but User model uses werkzeug.security
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db
from models.user import User

app = create_app('development')

with app.app_context():
    # Find super admin
    sa = User.query.filter_by(role='super_admin').first()
    if sa:
        print(f"Found super admin: email='{sa.email}', status='{sa.status}'")
        
        # Fix email to have proper domain
        if '@' not in sa.email:
            sa.email = 'kprem@rayatbahra.edu'
            print(f"Fixed email to: {sa.email}")
        
        # Re-set password using the model's werkzeug-based method
        sa.set_password("Prem@2004")
        
        db.session.commit()
        print(f"Password re-set using werkzeug.security")
        
        # Verify it works
        if sa.check_password("Prem@2004"):
            print("✓ Password verification successful!")
        else:
            print("✗ Password verification FAILED!")
    else:
        print("No super admin found in database!")
        print("Creating super admin user...")
        sa = User(
            email='kprem@rayatbahra.edu',
            role='super_admin',
            first_name='Prem',
            last_name='Kumar',
            phone='+91-9876543210',
            is_email_verified=True,
            status='active',
        )
        sa.set_password("Prem@2004")
        db.session.add(sa)
        db.session.commit()
        print("✓ Super admin created")
        if sa.check_password("Prem@2004"):
            print("✓ Password verification successful!")
    
    print("\n=== Final state ===")
    users = User.query.filter_by(role='super_admin').all()
    for u in users:
        print(f"  email='{u.email}', status='{u.status}'")
        pw_ok = u.check_password("Prem@2004")
        print(f"  Password 'Prem@2004' works: {pw_ok}")

