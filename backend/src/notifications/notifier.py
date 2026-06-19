"""
WillGuard EmailJS Notification Service
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Email notifications via EmailJS REST API for Guardian/Lockdown alerts.
Supports Magic Link restore: embedded link in email restores system to Co-Pilot.
Falls back to simulation mode when EmailJS is not configured.
"""

import os
import requests
from typing import Optional


class EmailNotifier:
    """
    Unified notification service for WillGuard.
    
    When EmailJS credentials are configured, sends real Emails.
    When not configured, operates in simulation mode (logs only).
    """

    def __init__(self):
        self.service_id = os.getenv("EMAILJS_SERVICE_ID", "")
        self.template_id = os.getenv("EMAILJS_TEMPLATE_ID", "")
        self.public_key = os.getenv("EMAILJS_PUBLIC_KEY", "")
        self.private_key = os.getenv("EMAILJS_PRIVATE_KEY", "")
        
        self.is_configured = bool(self.service_id and self.template_id and self.public_key)

        if self.is_configured:
            print(f"[EmailJS] ✅ Configured with Service ID: {self.service_id}")
        else:
            print("[EmailJS] ℹ️ Not configured — running in simulation mode")

    def _send_emailjs_post(self, to_email: str, message: str, magic_link: str = "") -> dict:
        """
        Send an email via EmailJS REST API.
        """
        if not self.is_configured:
            print(f"[EmailJS SIM] 📧 Would send to {to_email}: {message[:60]}...")
            return {
                "status": "simulated",
                "to": to_email,
                "body": message,
                "sid": None,
                "channel": "simulated_email",
            }

        payload = {
            "service_id": self.service_id,
            "template_id": self.template_id,
            "user_id": self.public_key,
            "accessToken": self.private_key,
            "template_params": {
                "to_email": to_email,
                "message": message,
                "magic_link": magic_link
            }
        }

        try:
            url = "https://api.emailjs.com/api/v1.0/email/send"
            response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
            
            if response.status_code == 200:
                print(f"[EmailJS] 📧 Email successfully dispatched to {to_email}")
                return {
                    "status": "sent",
                    "to": to_email,
                    "body": message,
                    "sid": "emailjs_sent",
                    "channel": "email",
                }
            else:
                print(f"[EmailJS] ❌ API Error: {response.text}")
                return {
                    "status": "failed",
                    "to": to_email,
                    "body": message,
                    "sid": None,
                    "error": response.text,
                    "channel": "email",
                }
                
        except Exception as e:
            print(f"[EmailJS] ❌ Request Failed: {e}")
            return {
                "status": "failed",
                "to": to_email,
                "body": message,
                "sid": None,
                "error": str(e),
                "channel": "email",
            }

    # ─── Pre-built Alert Templates ────────────────────────

    def send_guardian_alert(self, contact_email: str, contact_name: str, user_name: str, magic_link: str = "") -> dict:
        msg = f"⚠️ WillGuard Alert: {user_name}'s trading account has entered Guardian Mode due to inactivity. All new trades are paused. No action needed yet.\n\nMAGIC LINK: {magic_link}"
        return self._send_emailjs_post(contact_email, msg, magic_link=magic_link)

    def send_lockdown_alert(self, contact_email: str, contact_name: str, user_name: str, magic_link: str) -> dict:
        msg = f"🚨 WillGuard LOCKDOWN: {user_name} has been unresponsive. All trading is FROZEN. Click the MAGIC LINK below to confirm they are okay and instantly restore the system to Co-Pilot mode.\n\nMAGIC LINK: {magic_link}"
        return self._send_emailjs_post(contact_email, msg, magic_link=magic_link)

    def send_test_alert(self, contact_email: str, contact_name: str, user_name: str) -> dict:
        msg = f"✅ WillGuard Test: This is a test alert from {user_name}'s system. EmailJS notifications are working correctly."
        return self._send_emailjs_post(contact_email, msg)

    def send_restore_confirmation(self, contact_email: str, user_name: str) -> dict:
        msg = f"✅ WillGuard Restored: {user_name}'s account has been successfully restored to Co-Pilot mode via Magic Link."
        return self._send_emailjs_post(contact_email, msg)

    def get_status(self) -> dict:
        """Get notification system status."""
        return {
            "configured": self.is_configured,
            "provider": "EmailJS",
            "mode": "live" if self.is_configured else "simulation",
        }
