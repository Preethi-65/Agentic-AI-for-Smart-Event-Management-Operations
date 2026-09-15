# Deployment Guide — Milestone 4: Event Intelligence & Enterprise Deployment

This document covers everything needed to install, configure, run, test
and prepare this application (Milestones 1–4, one integrated codebase)
for production deployment.

> **Honesty note:** this project was built, tested and verified to run
> correctly with a production WSGI server (gunicorn, confirmed working
> below) inside its development environment. It has **not** been pushed
> to a live cloud provider (no AWS/Render/Azure account exists in the
> build environment), matching the brief's explicit fallback: *"If
> actual cloud deployment cannot be performed in the available
> environment, implement production-ready configuration and provide
> clear deployment instructions instead."* Everything below is real and
> verified locally, not aspirational.

## 1. Install dependencies

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Configure environment variables

```bash
cp .env.example .env
# then edit .env: set a real SECRET_KEY, and SMTP_* if you want real
# emails instead of simulation mode.
```

All configuration is centralized in `config.py` (`Config` class) and
read via `python-dotenv`. If `.env` is absent, safe local-development
defaults are used automatically (identical to the original M1–M3
behavior), so nothing breaks for a developer who skips this step.

## 3. Initialize the database

```bash
python -c "import database; database.init_db()"
```

Creates every M1+M2+M3+M4 table if it doesn't already exist (safe to
run repeatedly; never deletes existing data) and auto-seeds Milestone 3
sponsor/incident/alert demo data on first run.

## 4. Seed demo/sample data

```bash
python seed_data.py
```

Populates Milestone 1 (attendees) and Milestone 2 (sessions, venue
bookings, speaker assignments, session analytics) through the real
application logic, so every dashboard and chart is populated
immediately.

## 5. Run the application locally (development)

```bash
python app.py
```

Then open http://127.0.0.1:5000. Uses the Flask/Werkzeug development
server -- fine for local use and demos, **not** for production traffic.

## 6. Run tests

```bash
python -m pytest tests/test_milestone4.py -v
```

20 tests / 28 sub-checks covering functional, integration, AI/agent,
API, workflow/orchestration, dashboard, performance, security and error
handling categories. Runs against a temporary throwaway database, never
your real `data/registration.db`. See `TESTING.md` for the full latest
run output.

## 7. Run with a production WSGI server

Linux/macOS (gunicorn):

```bash
gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
```

Windows (gunicorn is Unix-only; use waitress):

```bash
waitress-serve --listen=0.0.0.0:8000 wsgi:app
```

Both were verified to serve every M1–M4 route correctly during this
build (see `TESTING.md`).

## 8. Container / PaaS deployment

A `Procfile` is included for Heroku-style platforms:

```
web: gunicorn -w 4 -b 0.0.0.0:$PORT wsgi:app
```

For any platform that reads a Procfile (Heroku, Render "Native
Runtime", Railway), set the environment variables from `.env.example`
in the platform's dashboard/secrets manager (never commit `.env`
itself) and deploy. For a container platform, wrap the same commands
in a Dockerfile with a `python:3.12-slim` base image, `pip install -r
requirements.txt`, and `CMD ["gunicorn", "-w", "4", "-b",
"0.0.0.0:8000", "wsgi:app"]`.

## 9. Reliability, security & scalability considerations

- **Secrets**: `SECRET_KEY` and SMTP credentials are environment
  variables only (`config.py`), never hardcoded or committed.
- **Input validation**: orchestration and incident-reporting routes
  validate required fields before touching the database and fail
  gracefully with a flashed message instead of a stack trace.
- **SQL safety**: every query in `database.py` uses parameterized
  queries (`?` / named placeholders) -- never string-formatted SQL --
  so the app is not vulnerable to SQL injection (verified in
  `tests/test_milestone4.py::test_17`).
- **Error handling**: global 404/500 handlers (`templates/error.html`)
  return a friendly page instead of leaking a stack trace; all 500s are
  logged via Python's `logging` module to `logs/app.log`.
- **Database**: SQLite is appropriate for this project's scale (single
  event, moderate concurrent users). For a genuinely multi-event,
  multi-organizer enterprise deployment, `DATABASE_PATH` can point at a
  mounted volume today, and the schema is portable enough for a future
  migration to PostgreSQL if concurrent write load grows.
- **Performance**: the Event Intelligence Engine caches its result for
  15 seconds (`agent/intelligence_engine.py::_CACHE`) so the Executive
  Dashboard and Intelligence Engine pages, which both call it, don't
  recompute cross-milestone aggregates on every request.
- **Backup**: the entire application state is one SQLite file
  (`data/registration.db`); back it up by copying that file (the
  server does not need to be stopped for SQLite's default journal
  mode, though a brief pause avoids any edge-case mid-write copy).
- **CI/CD readiness**: `tests/test_milestone4.py` is a self-contained,
  side-effect-free test suite (throwaway DB) suitable for a CI
  pipeline step (`pip install -r requirements.txt && python -m pytest
  tests/`) before any deploy step runs.

## 10. Rollback

Because Milestone 4 only ever *adds* new tables, routes and files (see
`README.md` → "Milestone 4" section for the exact diff surface), a
faulty M4 deploy can be rolled back by reverting `app.py`,
`database.py`, `config.py`, and the `agent/intelligence_engine.py` /
`agent/orchestrator.py` files to their pre-M4 versions -- no M1-M3
table or route is altered, so no data migration is required to roll
back.
