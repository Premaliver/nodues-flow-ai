"""
Interactive Live WhatsApp Tester for Smart NoDues AI.
Run with: python test_whatsapp_live_send.py <your_phone_number>
Example: python test_whatsapp_live_send.py 9876543210
"""

import sys
import os
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.whatsapp import format_phone_e164, build_admit_card_whatsapp_message

def test_live_send():
    phone_input = sys.argv[1] if len(sys.argv) > 1 else input("Enter your mobile number to test WhatsApp alert (e.g. 9876543210): ").strip()
    if not phone_input:
        print("[ERROR] Please provide a valid mobile number.")
        return

    phone_e164 = format_phone_e164(phone_input)
    clean_digits = phone_e164.lstrip("+")
    print(f"\n[INFO] Target Mobile Number: {phone_e164} (Digits: {clean_digits})")

    # Check UltraMsg credentials
    ultramsg_instance = os.environ.get("ULTRAMSG_INSTANCE_ID") or os.environ.get("ULTRAMSG_INSTANCE")
    ultramsg_token = os.environ.get("ULTRAMSG_TOKEN")

    # Check Twilio credentials
    twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    twilio_token = os.environ.get("TWILIO_AUTH_TOKEN")
    twilio_from = os.environ.get("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

    # Check Meta Cloud API credentials
    meta_token = os.environ.get("WHATSAPP_API_TOKEN")
    meta_phone_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")

    message_text = build_admit_card_whatsapp_message(
        student_name="Test Student",
        roll_number="24011011000",
        application_number="ND-2026-TEST",
        card_number="AC-24011011000-6-LIVE",
        semester_number=6,
        academic_year="2025-2026",
        course_name="B.Tech Computer Science Engineering",
        university_name="Rayat Bahra University",
        portal_url="http://127.0.0.1:5000"
    )

    print("\n--- Message Payload ---")
    print(message_text)
    print("-----------------------\n")

    # 1. UltraMsg Gateway Test
    if ultramsg_instance and ultramsg_token:
        print(f"[ATTEMPT] Sending via UltraMsg Gateway (Instance: {ultramsg_instance})...")
        try:
            url = f"https://api.ultramsg.com/{ultramsg_instance}/messages/chat"
            payload = {
                "token": ultramsg_token,
                "to": clean_digits,
                "body": message_text
            }
            resp = requests.post(url, data=payload, timeout=12)
            print("Response Status Code:", resp.status_code)
            print("Response Data:", resp.text)
            if resp.status_code == 200:
                print("\n[SUCCESS] Real WhatsApp message delivered to", phone_e164)
                return
            else:
                print("\n[FAILED] UltraMsg error:", resp.text)
        except Exception as e:
            print("[EXCEPTION] UltraMsg call failed:", str(e))

    # 2. Twilio WhatsApp Test
    elif twilio_sid and twilio_token:
        print(f"[ATTEMPT] Sending via Twilio WhatsApp Gateway...")
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json"
            auth = (twilio_sid, twilio_token)
            payload = {
                "From": twilio_from,
                "To": f"whatsapp:{phone_e164}",
                "Body": message_text
            }
            resp = requests.post(url, auth=auth, data=payload, timeout=12)
            print("Response Status Code:", resp.status_code)
            print("Response Data:", resp.text)
            if resp.status_code in [200, 201]:
                print("\n[SUCCESS] Real WhatsApp message delivered to", phone_e164)
                return
            else:
                print("\n[FAILED] Twilio error:", resp.text)
        except Exception as e:
            print("[EXCEPTION] Twilio call failed:", str(e))

    # 3. Meta Cloud API Test
    elif meta_token and meta_phone_id:
        print(f"[ATTEMPT] Sending via Meta WhatsApp Cloud API...")
        try:
            url = f"https://graph.facebook.com/v18.0/{meta_phone_id}/messages"
            headers = {
                "Authorization": f"Bearer {meta_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "messaging_product": "whatsapp",
                "to": clean_digits,
                "type": "text",
                "text": { "body": message_text }
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=12)
            print("Response Status Code:", resp.status_code)
            print("Response Data:", resp.text)
            if resp.status_code in [200, 201]:
                print("\n[SUCCESS] Real WhatsApp message delivered to", phone_e164)
                return
            else:
                print("\n[FAILED] Meta error:", resp.text)
        except Exception as e:
            print("[EXCEPTION] Meta call failed:", str(e))

    else:
        print("[NOTICE] No WhatsApp Gateway credentials configured in .env file yet!")
        print("Please add ULTRAMSG_INSTANCE_ID & ULTRAMSG_TOKEN in your .env file to enable automatic delivery.")

if __name__ == "__main__":
    test_live_send()
