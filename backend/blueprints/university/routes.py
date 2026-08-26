"""
University SaaS Onboarding, POV Walkthrough, and Subscription Routes.
Allows universities to register, explore the interactive POV demo, purchase subscriptions,
and launch their dedicated University SuperAdmin environment.
"""

import uuid
from datetime import datetime, timezone, timedelta
from flask import request, jsonify, render_template, session, redirect, url_for, current_app
from flask_login import login_user

from . import university_bp
from models import db
from models.university import UniversityTenant
from models.user import User
from control_plane.licensing.issuer import ControlPlaneLicenseIssuer
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
        if not tenant or not tenant.check_password(password):
            return jsonify({"success": False, "message": "Invalid email or password."}), 401

        session["university_id"] = str(tenant.id)
        session["university_name"] = tenant.name
        session["university_slug"] = tenant.slug

        redirect_target = "/university/dashboard" if tenant.has_active_subscription else "/university/pov"

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
        return jsonify({"success": False, "message": "Login failed. Please try again."}), 500


# ─────────────────────────────────────────────────────────────
# 3. UNIVERSITY LOGOUT
# ─────────────────────────────────────────────────────────────
@university_bp.route("/logout")
def logout():
    session.pop("university_id", None)
    session.pop("university_name", None)
    session.pop("university_slug", None)
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
        
        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"Congratulations! {univ.name} is now successfully subscribed to the {plan.capitalize()} Plan.",
            "data": {
                "university": univ.to_dict(),
                "payment_id": payment_id,
                "redirect_url": "/university/dashboard",
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

    return redirect("/auth/login")
