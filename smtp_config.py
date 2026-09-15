"""
smtp_config.py
---------------
Central configuration for the Event Notification & Reminder System
(see notifications.py).

Fill in real SMTP credentials below to send live emails. Until then,
SMTP_ENABLED stays False and the system runs in "simulation mode":
every confirmation and reminder email is still fully composed
(subject, HTML body, QR code) but is written to the Notification Log
(database table `notification_log`, visible on the Notifications page)
instead of actually being delivered. Nothing else has to change once
credentials are added — just fill these in and set SMTP_ENABLED = True.

Example for Gmail (use an "App Password", not your normal password):
    SMTP_HOST      = "smtp.gmail.com"
    SMTP_PORT      = 587
    SMTP_USE_TLS   = True
    SMTP_USERNAME  = "yourevent@gmail.com"
    SMTP_PASSWORD  = "xxxx xxxx xxxx xxxx"   # 16-char app password
    FROM_EMAIL     = "yourevent@gmail.com"

Example for Outlook / Office365:
    SMTP_HOST      = "smtp.office365.com"
    SMTP_PORT      = 587
    SMTP_USE_TLS   = True
"""

# Master switch — flip to True once the credentials below are filled in.
SMTP_ENABLED = False

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USE_TLS = True

SMTP_USERNAME = ""     # e.g. "yourevent@gmail.com"
SMTP_PASSWORD = ""     # e.g. app-specific password

FROM_EMAIL = ""        # defaults to SMTP_USERNAME if left blank
FROM_NAME = "Registration Intelligence Team"

# Organization / event branding used in email templates.
ORG_NAME = "Registration Intelligence & Attendee Management"

# How often (in seconds) the background reminder scheduler checks for
# due reminder emails. 6 hours is plenty for a same-day reminder to go
# out promptly without hammering the SMTP server.
REMINDER_CHECK_INTERVAL_SECONDS = 6 * 60 * 60
