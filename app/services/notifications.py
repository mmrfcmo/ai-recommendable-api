"""Email notification service."""
import smtplib
import os
from email.mime.text import MIMEText


def send_notification(subject: str, html_body: str):
    """Send an email notification."""
    gmail_user = os.environ.get("GMAIL_EMAIL", "")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD", "")
    if not gmail_user or not gmail_password:
        return

    msg = MIMEText(html_body, "html")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = "info@ai-recommendable.com"

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_password)
            server.send_message(msg)
    except Exception:
        pass


def send_report_notification(business_name: str, email: str, score: int, grade: str, report_url: str):
    """Send notification about a new Discoverability Assessment."""
    full_url = f"https://ai-recommendable-api.onrender.com{report_url}" if report_url else ""
    html = f"""<!DOCTYPE html><html><body style="font-family:Inter,sans-serif;background:#f8fafc;padding:2rem;margin:0">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.06)">
<div style="background:linear-gradient(135deg,#0f172a,#1e293b);padding:2rem;text-align:center">
<h1 style="color:white;margin:0;font-size:1.5rem">New Discoverability Assessment</h1></div>
<div style="padding:2rem">
<table style="width:100%;border-collapse:collapse">
<tr><td style="padding:.5rem 0;color:#64748b;font-size:.875rem">Business</td><td style="padding:.5rem 0;font-weight:600;text-align:right">{business_name}</td></tr>
<tr><td style="padding:.5rem 0;color:#64748b;font-size:.875rem">Email</td><td style="padding:.5rem 0;font-weight:600;text-align:right">{email}</td></tr>
<tr><td style="padding:.5rem 0;color:#64748b;font-size:.875rem">Score</td><td style="padding:.5rem 0;font-weight:600;text-align:right">{score}/100 ({grade})</td></tr>
</table>
<div style="text-align:center;margin:1.5rem 0">
<a href="{full_url}" style="display:inline-block;padding:.75rem 2rem;background:#f59e0b;color:white;text-decoration:none;border-radius:8px;font-weight:600">View Report →</a></div>
</div></div></body></html>"""
    send_notification(f"New Discoverability Assessment: {business_name}", html)


def send_assessment_notification(email: str, business_name: str, score: int, grade: str):
    """Send notification about a new readiness assessment."""
    html = f"""<!DOCTYPE html><html><body style="font-family:Inter,sans-serif;background:#f8fafc;padding:2rem;margin:0">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.06)">
<div style="background:linear-gradient(135deg,#0f172a,#1e293b);padding:2rem;text-align:center">
<h1 style="color:white;margin:0;font-size:1.5rem">New AI Readiness Assessment</h1></div>
<div style="padding:2rem">
<table style="width:100%;border-collapse:collapse">
<tr><td style="padding:.5rem 0;color:#64748b;font-size:.875rem">Business</td><td style="padding:.5rem 0;font-weight:600;text-align:right">{business_name or "Not provided"}</td></tr>
<tr><td style="padding:.5rem 0;color:#64748b;font-size:.875rem">Email</td><td style="padding:.5rem 0;font-weight:600;text-align:right">{email}</td></tr>
<tr><td style="padding:.5rem 0;color:#64748b;font-size:.875rem">Score</td><td style="padding:.5rem 0;font-weight:600;text-align:right">{score}/100 ({grade})</td></tr>
</table></div></div></body></html>"""
    send_notification(f"New AI Readiness Assessment: {business_name or email}", html)


def send_booking_notification(name: str, email: str, phone: str, message: str):
    """Send notification about a new consultation booking."""
    html = f"""<!DOCTYPE html><html><body style="font-family:Inter,sans-serif;background:#f8fafc;padding:2rem;margin:0">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.06)">
<div style="background:linear-gradient(135deg,#0f172a,#1e293b);padding:2rem;text-align:center">
<h1 style="color:white;margin:0;font-size:1.5rem">New Consultation Booking</h1></div>
<div style="padding:2rem">
<table style="width:100%;border-collapse:collapse">
<tr><td style="padding:.5rem 0;color:#64748b;font-size:.875rem">Name</td><td style="padding:.5rem 0;font-weight:600;text-align:right">{name}</td></tr>
<tr><td style="padding:.5rem 0;color:#64748b;font-size:.875rem">Email</td><td style="padding:.5rem 0;font-weight:600;text-align:right">{email}</td></tr>
<tr><td style="padding:.5rem 0;color:#64748b;font-size:.875rem">Phone</td><td style="padding:.5rem 0;font-weight:600;text-align:right">{phone or "Not provided"}</td></tr>
<tr><td style="padding:.5rem 0;color:#64748b;font-size:.875rem">Message</td><td style="padding:.5rem 0;font-weight:600;text-align:right">{message[:100] if message else "None"}</td></tr>
</table></div></div></body></html>"""
    send_notification(f"New Booking: {name}", html)