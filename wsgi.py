"""
wsgi.py
-------
Production WSGI entry point. The Flask development server used by
`python app.py` (Werkzeug) is not designed for production traffic; a
real deployment should point a WSGI server such as gunicorn or waitress
at this module instead.

Local production-style run (Linux/macOS):
    gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app

Local production-style run (Windows, gunicorn is Unix-only):
    waitress-serve --listen=0.0.0.0:8000 wsgi:app

Both commands are exercised in DEPLOYMENT.md.
"""

import database
import scheduler
from app import app

# Ensure the schema exists and the reminder scheduler is running even
# when this module is imported by a WSGI server rather than executed
# directly (python app.py only runs this under `if __name__ == "__main__"`).
database.init_db()
scheduler.start()

if __name__ == "__main__":
    app.run()
