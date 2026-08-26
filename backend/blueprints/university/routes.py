import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from flask import request, jsonify, render_template, session, redirect, url_for, current_app
from flask_login import login_user

# Ensure project root is in sys.path so control_plane is always importable
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from . import university_bp
from models import db
from models.university import UniversityTenant
from models.user import User

try:
    from control_plane.licensing.issuer import ControlPlaneLicenseIssuer
except ImportError:
    # Fallback to in-tree licensing manager
    from licensing.license_manager import LicenseManager as ControlPlaneLicenseIssuer

from licensing.crypto import LicenseCrypto


def get_current_university():
    """Helper to fetch logged-in university from session."""
    univ_id = session.get("university_id")
    if not univ_id:
        return None
    try:
        db.create_all()
        return UniversityTenant.query.get(uuid.UUID(str(univ_id)))
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
# 1. UNIVERSITY REGISTRATION
# ─────────────────────────────────────────────────────────────
@university_bp.route("/register", methods=["GET", "POST"])
def register():
    """University institutional registration portal."""
    if request.method == "GET":
        return render_template("university/register.html")

    data = request.get_json(silent=True) or request.form

    name = data.get("name", "").strip()
    official_email = data.get("official_email", "").strip().lower()
    password = data.get("password", "")
    contact_person = data.get("contact_person", "").strip()
    designation = data.get("designation", "Registrar / Dean").strip()
    phone = data.get("phone", "").strip()
    website = data.get("website", "").strip()
    state = data.get("state", "").strip()
    
    try:
        estimated_students = int(data.get("estimated_students", 5000))
    except (ValueError, TypeError):
        estimated_students = 5000

    if not name or not official_email or not password or not contact_person:
        return jsonify({"success": False, "message": "University name, official email, contact person, and password are required."}), 400

    try:
        db.create_all()
        # Check for existing
        existing = UniversityTenant.query.filter_by(official_email=official_email).first()
        if existing:
            return jsonify({"success": False, "message": "An account with this official email is already registered. Please log in instead."}), 409

        # Generate slug from name
        words = [ "".join(c.lower() for c in w if c.isalnum()) for w in name.split() ]
        base_slug = "-".join(w for w in words if w)[:30] or "univ"
        slug = base_slug
        counter = 1
        while UniversityTenant.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        tenant = UniversityTenant(
            name=name,
            slug=slug,
            official_email=official_email,
            contact_person=contact_person,
            designation=designation,
            phone=phone,
            website=website,
            state=state,
            estimated_students=estimated_students,
            subscription_status="unsubscribed",
            subscription_plan="none",
        )
        tenant.set_password(password)
        db.session.add(tenant)
        db.session.commit()

        # Log into session
        session["university_id"] = str(tenant.id)
        session["university_name"] = tenant.name
        session["university_slug"] = tenant.slug

        if request.is_json:
            return jsonify({
                "success": True,
                "message": f"University '{tenant.name}' registered successfully!",
                "data": {
                    "redirect_url": "/university/pov",
                    "university": tenant.to_dict(),
                }
            }), 201

        return redirect(url_for("university.pov"))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during university registration: {e}")
        return jsonify({"success": False, "message": f"Registration error: {str(e)}"}), 500


# ─────────────────────────────────────────────────────────────
# 2. UNIVERSITY LOGIN
# ─────────────────────────────────────────────────────────────
@university_bp.route("/login", methods=["GET", "POST"])
def login():
    """University leadership authentication portal."""
    if request.method == "GET":
        return render_template("university/login.html")

    data = request.get_json(silent=True) or request.form
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"success": False, "message": "Official email and password are required."}), 400

    try:
        db.create_all()
        tenant = UniversityTenant.query.filter_by(official_email=email).first()
        if not tenant:
            return jsonify({"success": False, "message": "No university registered with this email. Please register first."}), 401

        if not tenant.check_password(password):
            return jsonify({"success": False, "message": "Incorrect password. Please verify and try again."}), 401

        session["university_id"] = str(tenant.id)
        session["university_name"] = tenant.name
        session["university_slug"] = tenant.slug

        # Auto-login as SuperAdmin user for the platform
        sa_user = User.query.filter_by(role="super_admin").first()
        if sa_user:
            login_user(sa_user)

        redirect_target = "/superadmin/dashboard" if tenant.has_active_subscription else "/university/pov"

        if request.is_json:
            return jsonify({
                "success": True,
                "message": f"Welcome back, {tenant.contact_person}!",
                "data": {
                    "redirect_url": redirect_target,
                    "university": tenant.to_dict(),
                }
            })

        return redirect(redirect_target)

    except Exception as e:
        current_app.logger.error(f"Login error: {e}")
        return jsonify({"success": False, "message": "Login error occurred. Please try again."}), 500


# ─────────────────────────────────────────────────────────────
# 3. UNIVERSITY LOGOUT
# ─────────────────────────────────────────────────────────────
@university_bp.route("/logout")
def logout():
    session.pop("university_id", None)
    session.pop("university_name", None)
    session.pop("university_slug", None)
    from flask_login import logout_user
    logout_user()
    return redirect("/university/login")


# ─────────────────────────────────────────────────────────────
# 4. INTERACTIVE POV & LIVE SIMULATOR ROOM
# ─────────────────────────────────────────────────────────────
@university_bp.route("/pov")
def pov():
    """Interactive Live Demonstration and Product POV."""
    univ = get_current_university()
    return render_template("university/pov.html", university=univ)


# ─────────────────────────────────────────────────────────────
# 5. UNIVERSITY DASHBOARD
# ─────────────────────────────────────────────────────────────
@university_bp.route("/dashboard")
def dashboard():
    """University Leadership Hub & Subscription Control Center."""
    univ = get_current_university()
    if not univ:
        return redirect("/university/login")
    return render_template("university/dashboard.html", university=univ)


# ─────────────────────────────────────────────────────────────
# 6. PRICING & SUBSCRIPTION CHECKOUT
# ─────────────────────────────────────────────────────────────
@university_bp.route("/pricing")
def pricing():
    """Subscription tiers and checkout page."""
    univ = get_current_university()
    return render_template("university/pricing.html", university=univ)


# ─────────────────────────────────────────────────────────────
# 7. API: SUBSCRIBE / ACTIVATE SUBSCRIPTION
# ─────────────────────────────────────────────────────────────
@university_bp.route("/api/subscribe", methods=["POST"])
def activate_subscription():
    """Processes payment and unlocks the university's dedicated instance."""
    univ = get_current_university()
    if not univ:
        return jsonify({"success": False, "message": "Please log in to your university account first."}), 401

    data = request.get_json(silent=True) or request.form
    plan = data.get("plan", "professional").lower()
    billing_cycle = data.get("billing_cycle", "annual").lower()

    if plan not in ("starter", "professional", "enterprise", "custom"):
        plan = "professional"

    # Plan costs (in INR)
    plan_costs = {
        "starter": 49999 if billing_cycle == "annual" else 4999,
        "professional": 149999 if billing_cycle == "annual" else 14999,
        "enterprise": 399999 if billing_cycle == "annual" else 39999,
        "custom": 799999,
    }
    amount = plan_costs.get(plan, 149999)
    duration_days = 365 if billing_cycle == "annual" else 30

    try:
        payment_id = f"PAY_{uuid.uuid4().hex[:10].upper()}"

        # Activate university subscription
        univ.activate_subscription(
            plan=plan,
            cycle=billing_cycle,
            duration_days=duration_days,
            payment_id=payment_id,
            amount=amount,
        )

        # Generate cryptographic license token
        try:
            keys = ControlPlaneLicenseIssuer.generate_platform_keypair()
            issuer = ControlPlaneLicenseIssuer(private_key_pem=keys["private_key_pem"])
            license_token = issuer.issue_license(
                tenant_id=str(univ.id),
                tenant_slug=univ.slug,
                university_name=univ.name,
                plan_name=plan,
                valid_days=duration_days,
                max_active_students=univ.estimated_students or 10000,
            )
            univ.license_token = license_token
        except Exception as e:
            current_app.logger.warning(f"License token minting notice: {e}")

        # Ensure a University SuperAdmin User account exists for this university
        sa_user = User.query.filter_by(role="super_admin").first()
        if sa_user:
            # Link / update name if needed
            sa_user.first_name = univ.contact_person.split()[0] if univ.contact_person else "University"
            sa_user.last_name = "Admin"
            login_user(sa_user)
        
        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"Congratulations! {univ.name} is now successfully subscribed to the {plan.capitalize()} Plan.",
            "data": {
                "university": univ.to_dict(),
                "payment_id": payment_id,
                "redirect_url": "/superadmin/dashboard",
            }
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Subscription activation error: {e}")
        return jsonify({"success": False, "message": f"Subscription error: {str(e)}"}), 500


# ─────────────────────────────────────────────────────────────
# 8. LAUNCH DEDICATED SUPER ADMIN PORTAL
# ─────────────────────────────────────────────────────────────
@university_bp.route("/launch-superadmin")
def launch_superadmin():
    """Transfers the university leader into the live SuperAdmin platform."""
    univ = get_current_university()
    if not univ:
        return redirect("/university/login")

    if not univ.has_active_subscription:
        return redirect("/university/pricing")

    # Set institutional context
    session["university_name"] = univ.name
    session["university_slug"] = univ.slug

    # Auto-login as Super Admin for direct access to their dashboard
    sa_user = User.query.filter_by(role="super_admin").first()
    if sa_user:
        login_user(sa_user)
        return redirect("/superadmin/dashboard")

    return redirect("/university/login")


@university_bp.route("/logout")
def university_logout():
    """Logout of university portal session and return to university login."""
    session.pop("university_id", None)
    session.pop("university_slug", None)
    session.pop("university_name", None)
    logout_user()
    return redirect("/university/login")


# ─────────────────────────────────────────────────────────────
# 9. WHITE-LABEL INSTITUTIONAL PORTAL & ROLLOUT HUB
# ─────────────────────────────────────────────────────────────

def render_university_portal(slug: str):
    """Render the official branded clearance portal for a specific university."""
    db.create_all()
    univ = UniversityTenant.query.filter_by(slug=slug.lower().strip()).first()
    if not univ:
        univ = UniversityTenant.query.filter(UniversityTenant.slug.ilike(f"%{slug}%")).first()
    
    if not univ:
        return render_template(
            "errors/error.html",
            title="University Portal Not Found",
            message=f"No institution found registered with slug '{slug}'. Please check the URL or contact your campus administration.",
            code=404
        ), 404

    return render_template("university/portal.html", university=univ)


@university_bp.route("/portal/<slug>")
def university_portal_alias(slug):
    """Direct alias to institutional portal."""
    return render_university_portal(slug)


@university_bp.route("/poster")
def university_poster():
    """Render ready-to-print official Campus Notice Board Circular & QR Poster."""
    univ = get_current_university()
    if not univ:
        return redirect("/university/login")
    return render_template("university/poster.html", university=univ)


@university_bp.route("/portal/<slug>/poster")
def university_slug_poster(slug):
    """Public printable poster for the university."""
    univ = UniversityTenant.query.filter_by(slug=slug.lower().strip()).first()
    if not univ:
        return redirect("/university/login")
    return render_template("university/poster.html", university=univ)


# ─────────────────────────────────────────────────────────────
# 10. SCOPED STUDENT REGISTRATION & LOGIN VIA UNIVERSITY PORTAL
# ─────────────────────────────────────────────────────────────

@university_bp.route("/portal/<slug>/api/student-register", methods=["POST"])
def portal_student_register(slug):
    """Self-registration for students on the university's branded portal."""
    univ = UniversityTenant.query.filter_by(slug=slug.lower().strip()).first()
    if not univ:
        return jsonify({"success": False, "message": "Invalid university portal."}), 404

    data = request.get_json(silent=True) or request.form
    first_name = data.get("first_name", "").strip()
    last_name = data.get("last_name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    phone = data.get("phone", "").strip()
    roll_number = data.get("roll_number", "").strip().upper()
    enrollment_number = data.get("enrollment_number", "").strip().upper() or roll_number
    branch = data.get("branch", "Computer Science & Engineering").strip()
    course_name = data.get("course_name", "B.Tech").strip()
    category = data.get("category", "day_scholar").strip().lower()
    father_name = (data.get("father_name") or data.get("parent_name") or "").strip()
    mother_name = data.get("mother_name", "").strip()
    guardian_phone = (data.get("guardian_phone") or data.get("parent_phone") or "").strip()
    hod_dept_name = data.get("hod_department", "").strip()
    city = data.get("city", "").strip()
    state = data.get("state", "").strip()
    
    try:
        current_semester = int(data.get("current_semester", 8))
    except (ValueError, TypeError):
        current_semester = 8

    if not first_name or not email or not password or not roll_number:
        return jsonify({"success": False, "message": "First name, official email, roll number, and password are required."}), 400

    from models.student import Student
    from models.department import Department
    from models.audit_log import AuditLog

    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({"success": False, "message": "An account with this email already exists. Please log in directly."}), 409

    existing_student = Student.query.filter_by(roll_number=roll_number).first()
    if existing_student:
        return jsonify({"success": False, "message": f"Roll number {roll_number} is already registered. Please log in directly."}), 409

    try:
        # Find or link academic HOD department
        acad_dept = None
        dept_lookup = hod_dept_name or branch
        if dept_lookup:
            acad_dept = Department.query.filter(Department.name.ilike(f"%{dept_lookup}%")).first()
            if not acad_dept:
                acad_dept = Department.query.filter_by(role="hod").first()

        user = User(
            email=email,
            phone=phone or None,
            role="student",
            first_name=first_name,
            last_name=last_name,
            status="active",
            is_email_verified=True,
            university_id=univ.id
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        student = Student(
            user_id=user.id,
            roll_number=roll_number,
            enrollment_number=enrollment_number,
            course_name=course_name,
            branch=branch,
            academic_department_id=acad_dept.id if acad_dept else None,
            current_semester=current_semester,
            batch_year=f"{datetime.now(timezone.utc).year - 4}-{datetime.now(timezone.utc).year}",
            admission_year=datetime.now(timezone.utc).year - 4,
            category=category if category in ("day_scholar", "hosteller", "transport_user", "scholarship", "hosteller_transport", "scholarship_hosteller", "scholarship_transport", "hosteller_scholarship_transport") else "day_scholar",
            father_name=father_name or None,
            mother_name=mother_name or None,
            guardian_phone=guardian_phone or phone or None,
            city=city or None,
            state=state or None,
            university_id=univ.id,
        )
        db.session.add(student)


        audit = AuditLog(
            user_id=user.id,
            action="create",
            resource_type="student",
            resource_id=user.id,
            details={"portal": univ.slug, "roll_number": roll_number}
        )
        db.session.add(audit)
        db.session.commit()

        login_user(user)
        session["login_source"] = "university_portal"
        session["portal_slug"] = univ.slug
        session["university_id"] = str(univ.id)
        session["university_name"] = univ.name
        session["university_slug"] = univ.slug
        session["user_role"] = user.role

        return jsonify({
            "success": True,
            "message": f"Registration successful! Welcome to {univ.name} Digital No-Dues Portal.",
            "data": {
                "redirect_url": "/student/dashboard",
                "user": user.to_dict(),
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Student registration error: {e}")
        return jsonify({"success": False, "message": f"Registration failed: {str(e)}"}), 500


@university_bp.route("/portal/<slug>/api/student-login", methods=["POST"])
def portal_student_login(slug):
    """Login for students on the university's branded portal using Roll No or Email."""
    univ = UniversityTenant.query.filter_by(slug=slug.lower().strip()).first()
    if not univ:
        return jsonify({"success": False, "message": "Invalid university portal."}), 404

    data = request.get_json(silent=True) or request.form
    identifier = data.get("identifier", "").strip().lower()
    password = data.get("password", "")

    if not identifier or not password:
        return jsonify({"success": False, "message": "Roll number/Email and password are required."}), 400

    from models.student import Student

    user = None
    if "@" in identifier:
        user = User.query.filter_by(email=identifier, role="student").first()
    else:
        student_rec = Student.query.filter(Student.roll_number.ilike(identifier)).first()
        if student_rec and student_rec.user:
            user = student_rec.user

    if not user or not user.check_password(password):
        return jsonify({"success": False, "message": "Invalid roll number/email or password."}), 401

    if not user.university_id:
        user.university_id = univ.id
        db.session.commit()

    login_user(user)
    session["login_source"] = "university_portal"
    session["portal_slug"] = univ.slug
    session["university_id"] = str(univ.id)
    session["university_name"] = univ.name
    session["university_slug"] = univ.slug
    session["user_role"] = user.role

    return jsonify({
        "success": True,
        "message": f"Welcome back, {user.first_name}!",
        "data": {
            "redirect_url": "/student/dashboard",
            "user": user.to_dict(),
        }
    })


# ─────────────────────────────────────────────────────────────
# 11. SCOPED DEPARTMENT STAFF LOGIN VIA UNIVERSITY PORTAL
# ─────────────────────────────────────────────────────────────

@university_bp.route("/portal/<slug>/api/staff-login", methods=["POST"])
def portal_staff_login(slug):
    """Department staff login for Accounts, Hostel, Mess, Transport, Scholarship, HOD, Examination."""
    univ = UniversityTenant.query.filter_by(slug=slug.lower().strip()).first()
    if not univ:
        return jsonify({"success": False, "message": "Invalid university portal."}), 404

    data = request.get_json(silent=True) or request.form
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    department_role = data.get("role", "accounts").strip().lower()

    if not email or not password:
        return jsonify({"success": False, "message": "Official departmental email and password are required."}), 400

    valid_roles = ["accounts", "hostel", "mess", "transport", "scholarship", "hod", "examination"]
    if department_role not in valid_roles:
        department_role = "accounts"

    user = User.query.filter_by(email=email, role=department_role).first()
    
    if not user:
        user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return jsonify({"success": False, "message": "Invalid staff credentials. Please contact your University SuperAdmin."}), 401

    if not user.university_id:
        user.university_id = univ.id
        db.session.commit()

    login_user(user)
    session["login_source"] = "university_portal"
    session["portal_slug"] = univ.slug
    session["university_id"] = str(univ.id)
    session["university_name"] = univ.name
    session["university_slug"] = univ.slug
    session["user_role"] = user.role

    target_dashboard = f"/{user.role}/dashboard"


    return jsonify({
        "success": True,
        "message": f"Authenticated as {user.first_name} ({user.role.upper()})",
        "data": {
            "redirect_url": target_dashboard,
            "user": user.to_dict(),
        }
    })


# ─────────────────────────────────────────────────────────────
# 12. UNIVERSITY ADMIN: BRANDING & CUSTOMIZATION API
# ─────────────────────────────────────────────────────────────

@university_bp.route("/api/branding", methods=["POST"])
def update_branding():
    """Update institutional branding (Logo, theme colors, notice text)."""
    univ = get_current_university()
    if not univ:
        return jsonify({"success": False, "message": "Please log in to your university account."}), 401

    data = request.get_json(silent=True) or request.form
    logo_url = data.get("logo_url", "").strip()
    primary_color = data.get("primary_color", "").strip()
    accent_color = data.get("accent_color", "").strip()
    banner_text = data.get("banner_text", "").strip()
    phone = data.get("phone", "").strip()
    website = data.get("website", "").strip()

    if logo_url:
        from utils.helpers import normalize_logo_url
        univ.logo_url = normalize_logo_url(logo_url)

    if primary_color and primary_color.startswith("#"):
        univ.primary_color = primary_color
    if accent_color and accent_color.startswith("#"):
        univ.accent_color = accent_color
    if banner_text is not None:
        univ.banner_text = banner_text
    if phone:
        univ.phone = phone
    if website:
        univ.website = website

    db.session.commit()
    return jsonify({
        "success": True,
        "message": "University branding updated successfully!",
        "data": univ.to_dict()
    })


# ─────────────────────────────────────────────────────────────
# 13. UNIVERSITY ADMIN: DEPARTMENT STAFF DISPATCH & MANAGEMENT
# ─────────────────────────────────────────────────────────────

STANDARD_DEPARTMENTS = [
    {"role": "accounts", "code": "ACC", "name": "Accounts & Finance Department", "icon": "💳"},
    {"role": "hostel", "code": "HST", "name": "Hostel & Residence Department", "icon": "🏢"},
    {"role": "mess", "code": "MSS", "name": "Mess & Dining Services", "icon": "🍲"},
    {"role": "transport", "code": "TRN", "name": "Transport & Bus Fleet", "icon": "🚌"},
    {"role": "scholarship", "code": "SCH", "name": "Scholarship & Financial Aid Cell", "icon": "🎓"},
    {"role": "hod", "code": "HOD", "name": "Head of Department (HOD - Academics)", "icon": "👔"},
    {"role": "examination", "code": "EXM", "name": "Examination & Evaluation Cell", "icon": "📝"},
]

@university_bp.route("/api/staff", methods=["GET"])
def get_department_staff():
    """Retrieve all 7 departmental accounts for the university."""
    univ = get_current_university()
    if not univ:
        return jsonify({"success": False, "message": "Please log in."}), 401

    staff_list = []
    for dept in STANDARD_DEPARTMENTS:
        role = dept["role"]
        user = User.query.filter_by(university_id=univ.id, role=role).first()
        if not user:
            user = User.query.filter_by(role=role).first()

        default_email = f"{role}@{univ.slug}.nodues.edu"
        staff_list.append({
            "role": role,
            "code": dept["code"],
            "name": dept["name"],
            "icon": dept["icon"],
            "assigned_user": {
                "id": str(user.id) if user else None,
                "first_name": user.first_name if user else f"{dept['name'].split()[0]}",
                "last_name": user.last_name if user else "Officer",
                "email": user.email if user else default_email,
                "status": user.status if user else "active",
            } if user else None,
            "default_email": default_email,
        })

    return jsonify({"success": True, "departments": staff_list})


@university_bp.route("/api/staff/provision", methods=["POST"])
def provision_department_staff():
    """Auto-provision / reset default accounts for all 7 clearance departments."""
    univ = get_current_university()
    if not univ:
        return jsonify({"success": False, "message": "Please log in."}), 401

    data = request.get_json(silent=True) or {}
    default_pwd = data.get("default_password", "Staff@Clearance2025")

    provisioned = []
    try:
        for dept in STANDARD_DEPARTMENTS:
            role = dept["role"]
            email = f"{role}@{univ.slug}.nodues.edu".lower()

            user = User.query.filter_by(email=email).first()
            if not user:
                user = User(
                    email=email,
                    role=role,
                    first_name=univ.name.split()[0],
                    last_name=f"{dept['code']} Officer",
                    status="active",
                    is_email_verified=True,
                    university_id=univ.id,
                )
                user.set_password(default_pwd)
                db.session.add(user)
            else:
                user.university_id = univ.id
                user.set_password(default_pwd)

            provisioned.append({
                "role": role,
                "department": dept["name"],
                "email": email,
                "password": default_pwd,
                "login_url": f"/u/{univ.slug}",
            })

        db.session.commit()
        return jsonify({
            "success": True,
            "message": "All 7 Department accounts provisioned successfully!",
            "credentials": provisioned,
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Staff provisioning error: {e}")
        return jsonify({"success": False, "message": f"Provisioning failed: {str(e)}"}), 500


# ─────────────────────────────────────────────────────────────
# 14. UNIVERSITY ADMIN: BULK STUDENT CSV IMPORT
# ─────────────────────────────────────────────────────────────

@university_bp.route("/api/students/bulk-import", methods=["POST"])
def bulk_import_students():
    """Bulk import student roster via CSV."""
    univ = get_current_university()
    if not univ:
        return jsonify({"success": False, "message": "Please log in."}), 401

    from models.student import Student
    import csv
    import io

    if "file" not in request.files:
        return jsonify({"success": False, "message": "No CSV file uploaded."}), 400

    csv_file = request.files["file"]
    if not csv_file.filename.endswith((".csv", ".txt")):
        return jsonify({"success": False, "message": "Please upload a valid CSV file."}), 400

    try:
        stream = io.StringIO(csv_file.stream.read().decode("utf-8-sig"), newline=None)
        reader = csv.DictReader(stream)

        imported_count = 0
        skipped_count = 0
        default_pwd = "Student@123"

        for row in reader:
            roll_no = row.get("roll_number") or row.get("Roll Number") or row.get("roll_no") or ""
            roll_no = roll_no.strip().upper()
            
            email = row.get("email") or row.get("Email") or ""
            email = email.strip().lower()

            first_name = row.get("first_name") or row.get("First Name") or row.get("name") or "Student"
            first_name = first_name.strip()
            last_name = row.get("last_name") or row.get("Last Name") or ""
            last_name = last_name.strip()

            branch = row.get("branch") or row.get("Branch") or "Computer Science"
            course = row.get("course") or row.get("Course") or "B.Tech"
            category = (row.get("category") or "day_scholar").strip().lower()

            if not roll_no:
                continue

            if not email:
                email = f"{roll_no.lower()}@{univ.slug}.nodues.edu"

            existing_student = Student.query.filter_by(roll_number=roll_no).first()
            if existing_student:
                skipped_count += 1
                continue

            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                skipped_count += 1
                continue

            user = User(
                email=email,
                role="student",
                first_name=first_name,
                last_name=last_name,
                status="active",
                is_email_verified=True,
                university_id=univ.id,
            )
            user.set_password(f"{roll_no}@2025" if len(roll_no) > 3 else default_pwd)
            db.session.add(user)
            db.session.flush()

            student = Student(
                user_id=user.id,
                roll_number=roll_no,
                enrollment_number=roll_no,
                course_name=course,
                branch=branch,
                current_semester=8,
                batch_year=f"{datetime.now(timezone.utc).year - 4}-{datetime.now(timezone.utc).year}",
                admission_year=datetime.now(timezone.utc).year - 4,
                category=category if category in ("day_scholar", "hosteller", "transport_user", "scholarship") else "day_scholar",
                university_id=univ.id,
            )
            db.session.add(student)
            imported_count += 1

        db.session.commit()
        return jsonify({
            "success": True,
            "message": f"Successfully imported {imported_count} students! ({skipped_count} duplicates skipped)",
            "imported_count": imported_count,
            "skipped_count": skipped_count,
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Bulk student import error: {e}")
        return jsonify({"success": False, "message": f"CSV processing error: {str(e)}"}), 500


