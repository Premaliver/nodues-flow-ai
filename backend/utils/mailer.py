"""
Smart NoDues AI - Email Service Utility
Handles sending transactional emails like OTP verification, notifications, and alerts.
"""

import logging
from flask import current_app, render_template_string
from flask_mail import Message

logger = logging.getLogger(__name__)


OTP_EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Password Reset OTP</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f8fafc; padding: 40px 10px;">
        <tr>
            <td align="center">
                <table role="presentation" width="100%" style="max-width: 520px; background-color: #ffffff; border-radius: 16px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); overflow: hidden; border: 1px solid #e2e8f0;">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); padding: 32px 24px; text-align: center;">
                            <div style="display: inline-block; width: 44px; height: 44px; background: rgba(255, 255, 255, 0.2); border-radius: 12px; line-height: 44px; color: #ffffff; font-size: 22px; font-weight: 700; margin-bottom: 8px;">
                                S
                            </div>
                            <h1 style="margin: 0; color: #ffffff; font-size: 22px; font-weight: 700; letter-spacing: -0.02em;">
                                {{ university_name }}
                            </h1>
                            <p style="margin: 4px 0 0 0; color: #e0e7ff; font-size: 14px; font-weight: 500;">
                                {{ app_name }} &bull; Password Reset
                            </p>
                        </td>
                    </tr>

                    <!-- Body Content -->
                    <tr>
                        <td style="padding: 36px 32px;">
                            <p style="margin: 0 0 16px 0; font-size: 16px; color: #334155;">
                                Hello <strong>{{ recipient_name }}</strong>,
                            </p>
                            <p style="margin: 0 0 24px 0; font-size: 14px; line-height: 1.6; color: #64748b;">
                                We received a request to reset your password for your <strong>{{ app_name }}</strong> account. Use the 6-digit One-Time Password (OTP) below to complete your verification:
                            </p>

                            <!-- OTP Box -->
                            <div style="background: #f1f5f9; border: 2px dashed #cbd5e1; border-radius: 12px; padding: 20px; text-align: center; margin-bottom: 24px;">
                                <div style="font-size: 36px; font-weight: 800; letter-spacing: 8px; color: #4f46e5; font-family: monospace;">
                                    {{ otp }}
                                </div>
                                <p style="margin: 8px 0 0 0; font-size: 12px; color: #94a3b8; font-weight: 500;">
                                    ⏱️ Valid for {{ expires_in_minutes }} minutes only
                                </p>
                            </div>

                            <div style="background-color: #fffbeb; border-left: 4px solid #f59e0b; padding: 12px 16px; border-radius: 6px; margin-bottom: 24px;">
                                <p style="margin: 0; font-size: 13px; color: #b45309; line-height: 1.5;">
                                    🔒 <strong>Security Warning:</strong> Never share this OTP with anyone, including college staff or administrators.
                                </p>
                            </div>

                            <p style="margin: 0; font-size: 13px; line-height: 1.5; color: #94a3b8;">
                                If you did not request a password reset, you can safely ignore this email. Your password will remain unchanged.
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 20px 32px; text-align: center;">
                            <p style="margin: 0; font-size: 12px; color: #94a3b8;">
                                &copy; {{ university_name }} &bull; {{ app_name }} Automated System
                            </p>
                            <p style="margin: 4px 0 0 0; font-size: 11px; color: #cbd5e1;">
                                This is an automated email, please do not reply directly.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def send_otp_email(recipient_email: str, recipient_name: str, otp: str, expires_in_minutes: int = 10) -> dict:
    """
    Send OTP email to user for password reset.
    Returns a dictionary with delivery status:
      - sent: True if successfully delivered via SMTP
      - simulated: True if SMTP not configured (logged to console / dev helper)
      - error: Optional error string if SMTP failed
    """
    try:
        from app import mail

        app_name = current_app.config.get("APP_NAME", "Smart NoDues AI")
        university_name = current_app.config.get("UNIVERSITY_NAME", "Rayat Bahra University")
        sender = current_app.config.get("MAIL_DEFAULT_SENDER", "Smart NoDues AI <noreply@smartnodue.in>")

        rendered_html = render_template_string(
            OTP_EMAIL_TEMPLATE,
            recipient_name=recipient_name,
            otp=otp,
            expires_in_minutes=expires_in_minutes,
            app_name=app_name,
            university_name=university_name,
        )

        mail_user = current_app.config.get("MAIL_USERNAME")
        mail_pass = current_app.config.get("MAIL_PASSWORD")

        # Check if real SMTP credentials are provided in .env
        if not mail_user or not mail_pass:
            logger.info("=" * 60)
            logger.info(f"📧 [DEV EMAIL SIMULATION] To: {recipient_email}")
            logger.info(f"🔑 RESET OTP CODE: >>> {otp} <<< (Valid for {expires_in_minutes} mins)")
            logger.info("=" * 60)
            print(f"\n[DEV MAIL SIMULATION] OTP for {recipient_email} is: >>> {otp} <<<\n")
            return {
                "success": True,
                "sent": False,
                "simulated": True,
                "otp": otp,
                "message": "SMTP not configured in .env. OTP printed to terminal."
            }

        msg = Message(
            subject=f"[{app_name}] Password Reset OTP: {otp}",
            sender=sender or mail_user,
            recipients=[recipient_email],
            html=rendered_html,
        )

        # If SMTP is configured, attempt sending
        mail.send(msg)
        logger.info(f"✓ Password reset OTP email successfully sent to {recipient_email}")
        return {
            "success": True,
            "sent": True,
            "simulated": False,
            "message": f"Password reset email sent to {recipient_email}"
        }

    except Exception as e:
        logger.warning(f"SMTP send notice/failed: {e}")
        # Always output OTP to console so development or demo is never blocked if internet/SMTP is down
        logger.info("=" * 60)
        logger.info(f"📧 [CONSOLE OTP FALLBACK] To: {recipient_email}")
        logger.info(f"🔑 RESET OTP CODE: >>> {otp} <<< (Valid for {expires_in_minutes} mins)")
        logger.info("=" * 60)
        print(f"\n[CONSOLE OTP FALLBACK] OTP for {recipient_email} is: >>> {otp} <<<\n")
        return {
            "success": True,
            "sent": False,
            "simulated": True,
            "otp": otp,
            "error": str(e),
            "message": f"SMTP delivery failed: {str(e)}. OTP available in console fallback."
        }
