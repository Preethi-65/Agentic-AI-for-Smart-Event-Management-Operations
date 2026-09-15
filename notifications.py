"""
notifications.py
------------------
Event Notification & Reminder System.

This module owns all outbound attendee communication:

  1. Registration confirmation emails (sent immediately after a
     successful registration) containing the event name, date, time,
     venue, registration ID and the attendee's QR code.
  2. Automatic reminder emails sent 3 days before, 1 day before, and
     on the day of the event (see `run_due_reminders`, driven by
     `scheduler.py`).

Every email is fully built (subject + HTML body + QR attachment)
regardless of whether SMTP credentials are configured. If
`smtp_config.SMTP_ENABLED` is False (the default, since no real
credentials ship with this project), the email is not sent over the
network -- instead it is recorded in the `notification_log` table so
the whole pipeline can be demonstrated and verified end-to-end. Once
real credentials are added to smtp_config.py and SMTP_ENABLED is set
to True, the exact same code path sends real email -- no other files
need to change.
"""

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from datetime import datetime, date

import smtp_config as cfg
import database

BASE_DIR = os.path.dirname(__file__)


def _from_header():
    email_addr = cfg.FROM_EMAIL or cfg.SMTP_USERNAME or "no-reply@example.com"
    return f"{cfg.FROM_NAME} <{email_addr}>" if cfg.FROM_NAME else email_addr


def _build_message(to_email, subject, html_body, qr_path=None):
    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["From"] = _from_header()
    msg["To"] = to_email

    alt = MIMEMultipart("alternative")
    msg.attach(alt)
    alt.attach(MIMEText(html_body, "html"))

    if qr_path:
        full_path = os.path.join(BASE_DIR, qr_path)
        if os.path.exists(full_path):
            with open(full_path, "rb") as f:
                img = MIMEImage(f.read())
            img.add_header("Content-ID", "<qrcode>")
            img.add_header("Content-Disposition", "inline", filename="qrcode.png")
            msg.attach(img)
    return msg


def _send(msg, to_email):
    """Attempt real delivery if SMTP is configured; otherwise simulate."""
    if not cfg.SMTP_ENABLED or not cfg.SMTP_USERNAME or not cfg.SMTP_PASSWORD:
        return False, ("SMTP not configured yet -- email composed and logged only. "
                        "Add credentials to smtp_config.py to send for real.")
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(cfg.SMTP_HOST, cfg.SMTP_PORT, timeout=15) as server:
            if cfg.SMTP_USE_TLS:
                server.starttls(context=context)
            server.login(cfg.SMTP_USERNAME, cfg.SMTP_PASSWORD)
            server.sendmail(msg["From"], [to_email], msg.as_string())
        return True, "Email sent successfully."
    except Exception as exc:  # pragma: no cover - network dependent
        return False, f"Failed to send email: {exc}"


def _event_block_html(event):
    if not event:
        return "<li><b>Event details:</b> to be announced</li>"
    return f"""
        <li><b>Event:</b> {event['name']}</li>
        <li><b>Date:</b> {event['event_date']}</li>
        <li><b>Time:</b> {event['event_time']}</li>
        <li><b>Venue:</b> {event.get('venue') or '-'}</li>
    """


def send_confirmation_email(attendee, event):
    """Sends (or simulates) the registration confirmation email."""
    subject = f"Registration Confirmed — {event['name'] if event else cfg.ORG_NAME}"
    html = f"""
    <div style="font-family:Arial,sans-serif;color:#1c2236;max-width:520px;">
      <h2 style="color:#6d5efc;">You're Registered! 🎉</h2>
      <p>Hi {attendee['full_name']},</p>
      <p>Thank you for registering with {cfg.ORG_NAME}. Your registration is confirmed.
         Please keep this email handy — the attached QR code is your entry pass and
         will be scanned at the venue for check-in.</p>
      <ul style="line-height:1.9;">
        <li><b>Registration ID:</b> {attendee['reg_code']}</li>
        {_event_block_html(event)}
        <li><b>Name:</b> {attendee['full_name']}</li>
        <li><b>Category:</b> {attendee.get('category', '-')}</li>
      </ul>
      <p>Your QR code is attached to this email. See you at the event!</p>
      <p style="color:#9aa3c0;font-size:12px;">This is an automated message from the
         Event Notification &amp; Reminder System.</p>
    </div>
    """
    msg = _build_message(attendee["email"], subject, html, attendee.get("qr_path"))
    ok, note = _send(msg, attendee["email"])
    database.log_notification(attendee["id"], "confirmation", ok, note)
    return ok, note


def send_reminder_email(attendee, event, when_label, days_left):
    subject = f"Reminder: {event['name']} is {when_label}"
    html = f"""
    <div style="font-family:Arial,sans-serif;color:#1c2236;max-width:520px;">
      <h2 style="color:#22d3c5;">Event Reminder ⏰</h2>
      <p>Hi {attendee['full_name']},</p>
      <p>This is a friendly reminder that <b>{event['name']}</b> is
         <b>{when_label}</b>.</p>
      <ul style="line-height:1.9;">
        {_event_block_html(event)}
        <li><b>Your Registration ID:</b> {attendee['reg_code']}</li>
      </ul>
      <p>Please bring your QR code (sent in your confirmation email) for quick
         check-in at the venue.</p>
      <p style="color:#9aa3c0;font-size:12px;">This is an automated message from the
         Event Notification &amp; Reminder System.</p>
    </div>
    """
    msg = _build_message(attendee["email"], subject, html, attendee.get("qr_path"))
    ok, note = _send(msg, attendee["email"])
    database.log_notification(attendee["id"], f"reminder_{days_left}d", ok, note)
    return ok, note


def run_due_reminders():
    """
    Scans every registered attendee, compares their event's date to
    today, and sends the 3-day / 1-day / day-of reminder emails that
    are due and have not already been sent. Idempotent -- safe to call
    as often as needed (manually, or from scheduler.py).

    Returns the number of reminder emails processed.
    """
    today = date.today()
    processed = 0

    for attendee in database.get_all_attendees():
        event = database.get_event_by_name(attendee.get("event"))
        if not event or not event.get("event_date"):
            continue
        try:
            ev_date = datetime.strptime(event["event_date"], "%Y-%m-%d").date()
        except ValueError:
            continue

        days_left = (ev_date - today).days

        if days_left == 3 and not attendee.get("reminder_3d_sent"):
            send_reminder_email(attendee, event, "in 3 days", 3)
            database.mark_reminder_sent(attendee["id"], "3d")
            processed += 1
        elif days_left == 1 and not attendee.get("reminder_1d_sent"):
            send_reminder_email(attendee, event, "tomorrow", 1)
            database.mark_reminder_sent(attendee["id"], "1d")
            processed += 1
        elif days_left == 0 and not attendee.get("reminder_0d_sent"):
            send_reminder_email(attendee, event, "today", 0)
            database.mark_reminder_sent(attendee["id"], "0d")
            processed += 1

    return processed
