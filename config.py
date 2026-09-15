"""
config.py
---------
Milestone 4 -- Platform Reliability, Security & Production-Ready
Deployment.

Centralizes all environment-driven configuration so secrets and
deployment-specific values (secret key, debug flag, host/port, database
path) never need to be hardcoded or committed to source control. Reads
from a `.env` file if present (see `.env.example`) or from real
environment variables in a production host -- both work the same way.

This keeps M1-M3 behavior identical when no environment variables are
set (all defaults match the original hardcoded values), while giving
Milestone 4 a real "configure via environment variables" story for
deployment, exactly as required by the brief.
"""

import os

# Load a local .env file if python-dotenv is installed and a .env file
# exists. Optional dependency -- the app must still run without it
# (e.g. in a container where real environment variables are injected).
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _env_bool(name, default=False):
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


class Config:
    # Flask secret key -- MUST be overridden via SECRET_KEY in any real
    # deployment. The fallback preserves the original M1-M3 behavior for
    # local development so nothing breaks if this file is dropped in.
    SECRET_KEY = os.environ.get("SECRET_KEY", "registration-intelligence-secret-key")

    DEBUG = _env_bool("FLASK_DEBUG", default=False)
    HOST = os.environ.get("FLASK_HOST", "127.0.0.1")
    PORT = int(os.environ.get("FLASK_PORT", "5000"))

    # Database path -- overridable so production can point at a mounted
    # volume instead of the repo's local data/ folder.
    DATABASE_PATH = os.environ.get("DATABASE_PATH", "")

    # SMTP (used by notifications.py -- simulation mode when unset,
    # exactly as documented in the Milestone 1/3 report).
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")

    # Logging
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    LOG_FILE = os.environ.get("LOG_FILE", os.path.join(
        os.path.dirname(__file__), "logs", "app.log"))

    @staticmethod
    def is_production():
        return _env_bool("PRODUCTION", default=False)
