"""
WhatsApp Notification Service for Smart NoDues AI.
Supports Meta WhatsApp Cloud API, Twilio, 1-Click WhatsApp Direct (wa.me), and Console Simulation.
"""

import os
import re
import urllib.parse
import requests
from flask import current_app


def format_phone_e164(phone: str) -> str:
    """
    Sanitize and format phone number to international E.164 standard.
    Defaults to Indian country code +91 if 10 digits are provided.
    """
    if not phone:
        return ""
    
    # Remove all non-digits except leading '+'
    cleaned = re.sub(r"[^\d+]", "", str(phone).strip())
    
    # If starts with +, remove + to inspect digits
    digits_only = cleaned.lstrip("+")
    
    # If 10 digits (Standard Indian mobile number), prepend 91
    if len(digits_only) == 10:
        return f"+91{digits_only}"
    
    # If 11 digits starting with 0, replace leading 0 with 91
    if len(digits_only) == 11 and digits_only.startswith("0"):
        return f"+91{digits_only[1:]}"
    
    # If already has country code (e.g. 919876543210 or +919876543210)
    if len(digits_only) >= 11:
        return f"+{digits_only}"
    
    return f"+{digits_only}" if digits_only else ""


def build_admit_card_whatsapp_message(
    student_name: str,
    roll_number: str,
    application_number: str,
    card_number: str,
    semester_number: int or str,
    academic_year: str,
    course_name: str,
    university_name: str = "Rayat Bahra University",
    portal_url: str = "http://127.0.0.1:5000",
) -> str:
    """Build the official university WhatsApp clearance and admit card alert message."""
    return (
        f"🎓 *{university_name.upper()} — NO-DUES CLEARANCE COMPLETED* 🎓\n\n"
        f"Dear *{student_name}* (Roll No: *{roll_number}*),\n\n"
        f"🎉 *Congratulations!* Your institutional No-Dues clearance application (*{application_number}*) has been *OFFICIALLY APPROVED* by all university departments:\n"
        f"✅ Academic HOD Department\n"
        f"✅ Accounts & Finance Department\n"
        f"✅ Hostel & Mess Department\n"
        f"✅ Transport & Scholarship\n"
        f"✅ Examination Branch\n\n"
        f"🎫 *Digital Admit Card & QR Examination Pass Generated:*\n"
        f"• Card Number: *{card_number}*\n"
        f"• Semester: *Semester {semester_number} ({academic_year})*\n"
        f"• Course: *{course_name}*\n"
        f"• Verification: *Cryptographic QR Enabled*\n\n"
        f"📲 *Download Your Admit Card PDF:* \n"
        f"👉 {portal_url}/student/dashboard\n\n"
        f"🔒 *Note:* Please take a color/clear printout or carry the verified digital PDF to the examination hall.\n\n"
        f"— *Smart NoDues AI System | Office of the Controller of Examinations*"
    )


def send_whatsapp_admit_card_alert(
    user,
    student,
    application,
    admit_card,
    semester,
) -> dict:
    """
    Send WhatsApp alert to student's phone number.
    Uses Meta Cloud API or Twilio if configured, with graceful fallback to 1-Click WhatsApp Direct (wa.me).
    """
    student_name = user.full_name if user else getattr(student, "student_name", "Student")
    roll_number = student.roll_number if student else "N/A"
    app_number = application.application_number if application else "ND-APP"
    card_number = admit_card.card_number if admit_card else "AC-CARD"
    sem_number = semester.semester_number if semester else "Current"
    academic_year = semester.academic_year if semester else "2025-2026"
    course_name = student.course_name if student else "Degree Course"
    
    # Strictly resolve student's registered mobile number
    raw_phone = None
    if user and hasattr(user, "phone") and user.phone:
        raw_phone = user.phone
    elif student and hasattr(student, "user") and student.user and student.user.phone:
        raw_phone = student.user.phone
    elif student and hasattr(student, "guardian_phone") and student.guardian_phone:
        raw_phone = student.guardian_phone
    elif student and hasattr(student, "user_id") and student.user_id:
        try:
            from models.user import User as UserModel
            u = UserModel.query.get(student.user_id)
            if u and u.phone:
                raw_phone = u.phone
        except Exception:
            pass

    phone_e164 = format_phone_e164(raw_phone or "")
    if not phone_e164:
        phone_e164 = "+919876543210"  # fallback only if student profile has no phone number recorded

    university_name = "Rayat Bahra University"
    portal_url = "http://127.0.0.1:5000"
    try:
        if current_app:
            university_name = current_app.config.get("UNIVERSITY_NAME", university_name)
    except Exception:
        pass

    message_text = build_admit_card_whatsapp_message(
        student_name=student_name,
        roll_number=roll_number,
        application_number=app_number,
        card_number=card_number,
        semester_number=sem_number,
        academic_year=academic_year,
        course_name=course_name,
        university_name=university_name,
        portal_url=portal_url,
    )

    # 1-Click WhatsApp Direct Web/App Link
    encoded_text = urllib.parse.quote(message_text)
    wa_direct_link = f"https://wa.me/{phone_e164.lstrip('+')}?text={encoded_text}"

    # Check for Meta WhatsApp Cloud API credentials
    meta_token = os.environ.get("WHATSAPP_API_TOKEN")
    meta_phone_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")

    # Check for Twilio WhatsApp credentials
    twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    twilio_token = os.environ.get("TWILIO_AUTH_TOKEN")
    twilio_from = os.environ.get("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

    api_sent = False
    api_provider = None
    error_msg = None

    # Meta Cloud API dispatch
    if meta_token and meta_phone_id:
        try:
            url = f"https://graph.facebook.com/v18.0/{meta_phone_id}/messages"
            headers = {
                "Authorization": f"Bearer {meta_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "messaging_product": "whatsapp",
                "to": phone_e164.lstrip("+"),
                "type": "text",
                "text": { "body": message_text }
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=8)
            if resp.status_code in [200, 201]:
                api_sent = True
                api_provider = "meta_cloud_api"
            else:
                error_msg = f"Meta API error {resp.status_code}: {resp.text}"
        except Exception as e:
            error_msg = f"Meta API exception: {str(e)}"

    # Twilio API dispatch
    elif twilio_sid and twilio_token:
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json"
            auth = (twilio_sid, twilio_token)
            payload = {
                "From": twilio_from,
                "To": f"whatsapp:{phone_e164}",
                "Body": message_text
            }
            resp = requests.post(url, auth=auth, data=payload, timeout=8)
            if resp.status_code in [200, 201]:
                api_sent = True
                api_provider = "twilio"
            else:
                error_msg = f"Twilio API error {resp.status_code}: {resp.text}"
        except Exception as e:
            error_msg = f"Twilio exception: {str(e)}"

    # Console simulation / Terminal Logging
    try:
        print("\n" + "=" * 70)
        print("[WHATSAPP ALERT SERVICE] -- NO-DUES CLEARANCE & ADMIT CARD READY")
        print("=" * 70)
        print(f"Recipient: {student_name} ({phone_e164})")
        print(f"Admit Card Number: {card_number}")
        print(f"Delivery Mode: {'LIVE API (' + str(api_provider) + ')' if api_sent else '1-CLICK WHATSAPP DIRECT / CONSOLE'}")
        if error_msg:
            print(f"Notice: {error_msg}")
        print(f"Direct WhatsApp Link: {wa_direct_link[:80]}...")
        print("=" * 70 + "\n")
    except Exception:
        pass

    return {
        "success": True,
        "api_sent": api_sent,
        "provider": api_provider or "whatsapp_direct_and_console",
        "phone": phone_e164,
        "wa_link": wa_direct_link,
        "message": message_text
    }
