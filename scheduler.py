"""
scheduler.py
------------
Lightweight, dependency-free background scheduler for the Event
Notification & Reminder System. Runs a daemon thread that periodically
calls `notifications.run_due_reminders()` so 3-day / 1-day / day-of
reminder emails go out automatically without any manual action.

No extra third-party packages are required -- this keeps the project's
dependency footprint identical to before while still delivering fully
automatic reminders. (Reminders can also always be triggered instantly
and on-demand from the Notifications page in the UI.)
"""

import threading
import time

import notifications
import smtp_config as cfg

_started = False
_lock = threading.Lock()


def _loop():
    while True:
        try:
            notifications.run_due_reminders()
        except Exception as exc:  # pragma: no cover
            print(f"[scheduler] reminder check failed: {exc}")
        time.sleep(cfg.REMINDER_CHECK_INTERVAL_SECONDS)


def start():
    """Starts the background reminder loop exactly once per process."""
    global _started
    with _lock:
        if _started:
            return
        _started = True
    thread = threading.Thread(target=_loop, name="reminder-scheduler", daemon=True)
    thread.start()
