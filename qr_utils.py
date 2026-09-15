"""
qr_utils.py
-----------
Generates and stores the unique QR code for each attendee, used by the
QR Code Check-in module.

The QR encodes a direct check-in URL (http://<host>/checkin/<reg_code>)
so that scanning it with any phone camera opens the check-in link
automatically. The Check-in Tracker page also includes an in-browser
camera scanner that reads the same QR codes without leaving the page.
"""

import os
import qrcode

QR_DIR = os.path.join(os.path.dirname(__file__), "static", "img", "qrcodes")


def generate_qr(reg_code: str, base_url: str = "") -> str:
    """
    Creates a PNG QR code for the given registration code and saves it
    under static/img/qrcodes/<reg_code>.png. Returns the path relative
    to the project root (suitable for both url_for('static', ...) style
    usage and for attaching the file to an email).
    """
    os.makedirs(QR_DIR, exist_ok=True)

    payload = f"{base_url.rstrip('/')}/checkin/{reg_code}" if base_url else reg_code

    img = qrcode.make(payload)
    filename = f"{reg_code}.png"
    filepath = os.path.join(QR_DIR, filename)
    img.save(filepath)

    return os.path.join("static", "img", "qrcodes", filename).replace("\\", "/")
