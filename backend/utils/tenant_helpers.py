"""Tenant isolation helpers for ensuring proper scoping across all entities."""

import uuid
from typing import Optional
from flask import session, request
from flask_login import current_user
from models import db
from models.department import Department
from models.university import UniversityTenant


STANDARD_DEPARTMENTS = [
    {"code": "LIB", "name": "Central Library", "role": "library", "display_order": 1},
    {"code": "HST", "name": "Hostel Administration", "role": "hostel", "display_order": 2},
    {"code": "MSS", "name": "Mess & Cafeteria", "role": "mess", "display_order": 3},
    {"code": "TRN", "name": "Transport Office", "role": "transport", "display_order": 4},
    {"code": "SCH", "name": "Scholarship & Grants", "role": "scholarship", "display_order": 5},
    {"code": "HOD", "name": "Academic Head of Department (HOD)", "role": "hod", "display_order": 6},
    {"code": "ACC", "name": "Accounts & Finance", "role": "accounts", "display_order": 7},
    {"code": "EXAM", "name": "Examination Department", "role": "examination", "display_order": 8},
]


def ensure_university_departments(university_id) -> None:
    """
    Ensure all standard institutional departments exist strictly for the given university_id.
    Prevents cross-tenant department fallback and data leakage.
    """
    if not university_id:
        return

    try:
        u_uuid = uuid.UUID(str(university_id)) if isinstance(university_id, str) else university_id
    except Exception:
        return

    existing_roles = {
        d.role for d in Department.query.filter_by(university_id=u_uuid).all()
    }

    created_any = False
    for d_spec in STANDARD_DEPARTMENTS:
        if d_spec["role"] not in existing_roles:
            dept = Department(
                university_id=u_uuid,
                code=d_spec["code"],
                name=d_spec["name"],
                role=d_spec["role"],
                display_order=d_spec["display_order"],
                is_active=True,
            )
            db.session.add(dept)
            created_any = True

    if created_any:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()


def get_current_context_university() -> Optional[UniversityTenant]:
    """Resolve the active university tenant object from session, logged-in user, JWT, or query params."""
    # 1. From authenticated user directly (Highest priority for logged-in sessions)
    if current_user and current_user.is_authenticated:
        if hasattr(current_user, "university_id") and current_user.university_id:
            try:
                u_uuid = uuid.UUID(str(current_user.university_id)) if isinstance(current_user.university_id, str) else current_user.university_id
                univ = db.session.get(UniversityTenant, u_uuid)
                if univ:
                    return univ
            except Exception:
                pass
        # Auto-heal super_admin missing university_id by matching official_email
        if getattr(current_user, "role", "") == "super_admin" and getattr(current_user, "email", None):
            try:
                matched = UniversityTenant.query.filter_by(official_email=current_user.email.strip().lower()).first()
                if matched:
                    current_user.university_id = matched.id
                    db.session.commit()
                    return matched
            except Exception:
                pass

    # 2. From request query params (e.g. ?u=slug or ?university=slug)
    query_slug = request.args.get("u") or request.args.get("university") or request.args.get("slug")
    if query_slug:
        univ = UniversityTenant.query.filter_by(slug=query_slug.strip().lower()).first()
        if univ:
            return univ

    # 3. From session university_id
    univ_id = session.get("university_id")

    # 4. From JWT token claims
    if not univ_id:
        try:
            from flask_jwt_extended import verify_jwt_in_request, get_jwt
            verify_jwt_in_request(optional=True)
            claims = get_jwt()
            if claims and claims.get("university_id"):
                univ_id = claims.get("university_id")
        except Exception:
            pass

    if univ_id:
        try:
            u_uuid = uuid.UUID(str(univ_id)) if isinstance(univ_id, str) else univ_id
            univ = db.session.get(UniversityTenant, u_uuid)
            if univ:
                return univ
        except Exception:
            pass

    # 5. From session slug / portal_slug
    univ_slug = session.get("university_slug") or session.get("portal_slug")
    if univ_slug:
        univ = UniversityTenant.query.filter_by(slug=univ_slug).first()
        if univ:
            return univ

    # 6. Fallback to default registered university
    try:
        return UniversityTenant.query.first()
    except Exception:
        return None

