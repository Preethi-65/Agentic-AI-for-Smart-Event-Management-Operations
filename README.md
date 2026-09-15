# Agentic AI for Smart Event Management Operations

**Milestone 1: Registration Intelligence and Attendee Management**
**Milestone 2: Agentic AI for Smart Event Management Operations**
(functional areas: Venue Agent, Speaker Agent, Venue Optimization
Workflows, Speaker Scheduling, Session Analytics)

A single, integrated Flask web application covering the full
lifecycle of running an event: attendee registration, QR check-in,
attendee analytics, automated notifications, and — new in Milestone 2
— AI-assisted venue selection/booking, speaker recommendation,
conflict-checked scheduling, and session analytics. Both milestones
share one codebase, one database, one UI, and one navigation menu —
this is one continuous project, not two separate apps.

## Technology Stack

Python 3 + Flask, SQLite (`sqlite3`), server-rendered Jinja2 templates,
vanilla HTML5/CSS3, Chart.js (CDN) for charts, `html5-qrcode` (CDN) for
camera QR scanning, `qrcode`+Pillow for QR generation, and Python's
built-in `smtplib` for email. No paid or external AI API is used —
Venue Agent and Speaker Agent "intelligence" is implemented with local,
transparent, rule-based scoring logic (see below), so the project runs
completely offline.

---

## Milestone 1 — Registration Intelligence and Attendee Management

1. **Registration Agent** (`agent/registration_agent.py`) — cleans
   input, validates mandatory fields (name, email, age, event), infers
   category, assigns a priority flag, detects duplicate emails,
   generates a unique registration code.
2. **Integrated Registration System** (`database.py`) — shared SQLite
   layer for every module.
3. **Attendee Analytics** (`/analytics`) — age group, city, gender,
   daily registrations, event popularity, check-in status, category,
   priority, and day-wise trend charts.
4. **QR Code Check-in** (`qr_utils.py`, `/checkin`, `/checkin/<code>`) —
   unique QR code per attendee; scanning (camera or link) checks them
   in, timestamps it, and blocks duplicate check-ins.
5. **Event Notification & Reminder System** (`notifications.py`,
   `scheduler.py`, `smtp_config.py`) — confirmation email on signup,
   automatic reminders 3 days / 1 day / day-of. Runs in simulation
   mode (logs every email) until SMTP credentials are added.
6. **Registration Dashboard** (`/dashboard`, home page) — live summary
   cards, six charts, auto-updating event countdown.

---

## Milestone 2 — Agentic AI for Smart Event Management Operations

Extends the same database and UI with five new functional areas
(Venue Agent, Speaker Agent, Venue Optimization Workflows, Speaker
Scheduling, Session Analytics):

### 1. Venue Agent (`agent/venue_agent.py`, `/venue-agent`)
Given attendee count, date/time, required facilities and an optional
preferred location, the agent:
- Filters venues by capacity, checks real-time availability against
  `venue_bookings` (no double-booking), and computes a **utilization
  %** for every candidate.
- Scores venues so a **right-sized, well-utilized venue is preferred
  over an oversized one** — e.g. for 150 attendees, a 200-capacity
  hall (75% utilization) outranks a 500-capacity hall (30%), even
  though both fit. See the "Agent decision" explanation banner shown
  in the UI for every search.
- If the best-fit venues are already booked, it still returns the
  best *available* alternative instead of leaving the organizer with
  nothing, and clearly labels it as a fallback.
- Booking is transactional: `database.create_booking()` re-checks for
  conflicts immediately before inserting, so two organizers can never
  double-book the same venue/slot.
- Bookings can be cancelled from `/venues`.

### 2. Speaker Agent (`agent/speaker_agent.py`, `/speaker-agent`)
Given a session topic and date/time, the agent ranks every speaker by
a transparent **Match Score** built from:
Topic/Expertise Match (40%) + Availability (20%) + Experience (15%) +
Rating (15%) + Schedule Compatibility (10%) — with the contributing
reasons shown directly in the UI (no black box).
- Speaker expertise lives in the `speaker_expertise` table, which is
  **not limited to a speaker's original profile** — the "Speaker
  Directory" tab includes a "+ Add Expertise" action to record that a
  speaker mentioned an additional topic while presenting. That topic
  is immediately searchable, demonstrating exactly the scenario from
  the brief (a speaker on Topic A who mentions expertise in Topic C
  becomes recommendable for Topic C afterwards).
- Conflict detection: assigning a speaker who already has an
  overlapping session re-checks at the moment of assignment and is
  rejected with **"Scheduling Conflict – Speaker is already assigned
  during this time,"** with alternative available speakers already
  ranked above/below it for the organizer to pick instead.

### 3. Sessions & Final Event Schedule (`/sessions`)
Create a session (title, topic, linked event, date/time, expected
attendees, facilities, location) and this same page doubles as the
**Final Integrated Event Schedule**: every session with its Venue,
Speaker, capacity and live status (Draft → Venue Booked → Speaker
Assigned → Confirmed) in one table.

### 4. Speaker Schedule (`/speaker-schedule`)
A conflict-free timeline of every speaker assignment, plus a workload
overview per speaker (sessions delivered, current expertise list).

### 5. Session Analytics (`/session-analytics`)
Dashboard cards (total sessions, avg attendance rate, avg rating, avg
venue occupancy) plus charts: Most Popular Sessions, Peak Attendance
Times, Venue Utilization, and Speaker Performance. Popularity is
computed transparently as 40% attendance rate + 40% average rating +
20% feedback volume — never from a single metric.

### Database additions (`database.py`)
`venues`, `venue_bookings`, `speakers`, `speaker_expertise`,
`sessions`, `speaker_assignments`, `session_analytics` — all created
automatically by `init_db()` alongside the existing Milestone 1
tables, in the same `data/registration.db` file. Sessions link to
Milestone 1 `events` via `sessions.event_name`.

---

## Project Structure

```
project/
├── app.py                       # All routes — Milestone 1 + Milestone 2
├── database.py                  # Shared SQLite layer (both milestones)
├── qr_utils.py                  # QR code generation (Milestone 1)
├── notifications.py             # Email confirmation + reminders (Milestone 1)
├── scheduler.py                 # Background reminder scheduler (Milestone 1)
├── smtp_config.py               # SMTP credentials (fill in to send real email)
├── seed_data.py                 # Demo data for BOTH milestones
├── requirements.txt
├── agent/
│   ├── registration_agent.py    # Milestone 1: Registration Agent
│   ├── venue_agent.py           # Milestone 2: Venue Agent
│   └── speaker_agent.py         # Milestone 2: Speaker Agent
├── data/registration.db         # Created automatically on first run
├── templates/
│   ├── base.html, dashboard.html, register.html, registration_success.html,
│   │   attendees.html, analytics.html, checkin.html, notifications.html   (Milestone 1)
│   └── sessions.html, venues.html, venue_agent.html, speaker_agent.html,
│       speaker_schedule.html, session_analytics.html                     (Milestone 2)
└── static/
    ├── css/style.css             # One shared stylesheet for the whole app
    └── img/qrcodes/               # Generated QR code PNGs
```

---

## How to Run in VS Code (Windows)

1. Open the project folder in VS Code (`File > Open Folder`).
2. Open a terminal (`` Ctrl+` ``) and create a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Load demo data for both milestones (recommended so every page has
   something to show immediately):
   ```
   python seed_data.py
   ```
5. Run the app:
   ```
   python app.py
   ```
6. Open **http://127.0.0.1:5000**

(macOS/Linux: use `source venv/bin/activate` and `python3` instead.)

The database is created and migrated automatically — no manual setup
needed. To reset everything, delete `data/registration.db` and the
contents of `static/img/qrcodes/`, then re-run `seed_data.py`.

---

## Demo Flow (for presenting to a mentor)

1. **Dashboard** — show the live cards, charts, and event countdown.
2. **Registration Agent** — register a new attendee (e.g. yourself);
   land on the confirmation page with the QR code.
3. **Check-in Tracker** — scan or type the code in; try it a second
   time to show the "Already Checked In" rejection.
4. **Attendee Analytics** — show the live charts.
5. **Sessions** — open `/sessions`, show the Final Integrated Event
   Schedule already populated by the seed data, then create a new
   session live.
6. **Venue Agent** — from the new session, click "Find Venue"; show
   the right-sized recommendation vs. the oversized alternative, then
   book it.
7. **Speaker Agent** — click "Find Speaker"; show the ranked list with
   Match Scores and reasons. Optionally demo a conflict: try assigning
   a speaker who's already busy (e.g. Dr. Anitha Raghavan at
   2026-08-05 10:30–11:30) to see the rejection, then assign the
   next-ranked available speaker instead.
8. **Speaker Directory tab** — use "+ Add Expertise" on a speaker to
   record a newly-mentioned topic, then re-run a recommendation for
   that topic to show them now appearing.
9. **Speaker Schedule** — show the conflict-free assignment list.
10. **Session Analytics** — show Most Popular Sessions and the
    transparent popularity-score explanation.

---

## Notes

- All Milestone 1 functionality (registration, QR check-in, analytics,
  notifications) is unchanged and fully working — Milestone 2 was
  added purely additively on top of it.
- No files were deleted; see `UPDATE_LOG.md` for the original
  Milestone 1 enhancement history and the Milestone 2 addition log.

---

## Milestone 3 — Sponsorship & Incident Management

Added purely additively on top of Milestones 1 and 2 — same Flask app,
same shared `data/registration.db`, same base template and navigation
menu, same CSS design language. Nothing above this section changed.

### 1. Sponsorship Agent (`agent/sponsorship_agent.py`, `/sponsorship-agent`)
Tracks every sponsor's package, contract, payment, branding and
performance metrics, and automatically answers:
- *Which sponsors have pending deliverables?*
- *Which sponsor has the highest attendee engagement?*
- *Which sponsors are at risk of not receiving their promised benefits?*

Performance label (Excellent / Good / At Risk) is a transparent
weighted score: 40% engagement + 30% deliverable completion + 30%
satisfaction (scaled to 100) — never a single metric.

### 2. Incident Agent (`agent/incident_agent.py`, `/incident-agent`)
Rule-based classification for 13 incident categories (speaker
cancellation, venue/AV/network/power failure, overcrowding, medical
emergency, security issue, session delay, missing equipment,
fire-related issue, etc.). For every incident it returns category,
severity, priority, affected area, responsible team, recommended
action and status — e.g. a Hall A microphone failure 10 minutes before
the next session is classified as Severity: Medium, Priority: High,
Team: AV Team, Action: "Replace the microphone / use a backup mic."
High-risk keywords in the description (fire, evacuate, unconscious,
etc.) force an automatic Critical escalation regardless of category.

### 3. Incident Alert System (`/alerts`)
Every incident automatically raises a linked alert in one of four
types — Critical, High-Priority, Medium-Priority, Informational — each
shown with its description, status and recommended action, with
Acknowledge/Resolve actions and filters by type/status.

### 4. Sponsor Performance Tracking (`/sponsor-performance`)
Dashboard covering engagement, leads generated, booth visits, session
participation, social engagement, deliverable completion, satisfaction
and conversion rate, with bar/donut charts and a sortable performance
table.

### 5. Milestone 3 Dashboard (`/milestone3-dashboard`)
KPI cards (sponsors, engagement, pending deliverables, leads,
incidents, alerts) plus six charts: sponsor performance distribution
(donut), sponsor engagement (bar), incidents by category (bar),
incidents over time (line), incident status (donut), and alerts by
type (bar) — all rendered from the seeded default dataset immediately
on first run.

### Chart reliability
Milestone 3's charts load Chart.js from a **locally vendored copy**
(`static/js/vendor/chart.umd.min.js`) instead of an external CDN, so
every chart renders even without an internet connection. (Milestone 1
and 2 charts are unchanged and continue to use the original CDN link,
per the "do not modify Milestone 1/2" requirement.)

### Database additions (`database.py`)
`sponsors`, `sponsor_deliverables`, `incidents`, `alerts` — created
automatically by `init_db()` in the same `data/registration.db` file,
seeded with 8 sponsors, 17 deliverables, 12 incidents and 17 alerts
(32+ records total) on first run so every chart, KPI and table is
populated immediately — no manual data entry required.

### New templates
`sponsorship_agent.html`, `sponsor_performance.html`,
`incident_agent.html`, `alerts.html`, `milestone3_dashboard.html` —
integrated into the same navigation sidebar as Milestones 1 and 2.

---

## Milestone 4 — Event Intelligence & Enterprise Deployment

Transforms the individual M1–M3 modules and agents into one integrated
intelligent event management system, added **entirely additively**:
no M1, M2 or M3 route, table, template or feature was removed,
redesigned or broken.

### 1. Event Intelligence Engine (`agent/intelligence_engine.py`)
The central intelligence layer. Pulls live data from Registration
(M1), Venue/Speaker/Session Analytics (M2) and Sponsorship/Incident
data (M3) via `database.get_all_data_for_intelligence_engine()` and
computes:
- An **Event Health Score** (0–100), starting at 100 and reduced only
  by named, explainable penalties (open Critical/High incidents,
  escalated incidents, low check-in rate, at-risk sponsor ratio, low
  session ratings) — never a black-box number.
- A prioritized **risk list** (Critical/High/Medium/Low) covering
  incidents, sponsorship, attendance and venue utilization.
- Concrete **AI recommendations** derived directly from the risks.
- A **KPI bundle** feeding the Executive Dashboard.

Like every other agent in this project, it is 100% rule-based and
local — no external or paid AI API. Results are cached for 15 seconds
(`_CACHE`) so repeated dashboard loads stay fast.

### 2. Agent Orchestration (`agent/orchestrator.py`, `/orchestration`)
Coordinates the existing agents on a single trigger instead of letting
them run independently. The implemented workflow — **Speaker
Cancellation Response** — is a real, runnable 7-step pipeline, not
documentation:

```
Speaker Agent → Event Intelligence Engine → Venue Agent →
Registration Agent → Incident Agent → Alert System → Executive Dashboard
```

Triggering it (via the `/orchestration` form) actually clears the
session's speaker, creates a real incident through
`incident_agent.classify_incident()`, raises a real alert, and
persists an intelligence snapshot — every step logged to the new
`orchestration_log` table for a full audit trail shown on the page.

### 3. Executive Dashboard (`/executive-dashboard`)
A high-level view for senior management — distinct from the
operational Milestone 3 Dashboard. Shows the overall Event Health
Score, Event Overview KPIs, Sponsor & Incident performance, top risks,
AI recommendations, sponsor performance distribution and the event
health trend — all computed live from the shared database, never
hardcoded.

### 4. Real-Time Decision Support
The Intelligence Engine and Executive Dashboard together answer the
brief's example questions directly: is the event healthy, what are
the major risks, which incidents need immediate attention, which
sponsors are at risk, is venue utilization efficient — each backed by
a concrete metric, not a vague statement.

### 5. Platform Reliability, Security & Performance
- `config.py` centralizes all environment-driven configuration
  (`SECRET_KEY`, debug flag, database path, SMTP, logging) — see
  `.env.example`.
- Global 404/500 error handlers (`templates/error.html`) instead of
  leaking stack traces; all exceptions logged to `logs/app.log`.
- Every database query remains parameterized (inherited from M1–M3) —
  no SQL injection surface, verified in `tests/test_milestone4.py`.
- Intelligence Engine result caching (15s TTL) avoids recomputing
  cross-milestone aggregates on every dashboard request.

### 6. Testing (`tests/test_milestone4.py`, `/testing-center`)
20 automated tests / 28 sub-checks covering functional, integration,
AI/agent, API, workflow, dashboard, performance, security, error
handling and user-acceptance categories, run against a disposable
temporary database. The **Testing Center page is a live subsystem, not
a document**: pressing "Run Full Test Suite" actually executes
`pytest` as a subprocess against the real project via
`agent/test_runner.py`, parses the results per test and per category,
and persists the run to the new `test_runs` table for history. See
`TESTING.md` for the full latest run output and manual end-to-end
verification notes (including a real gunicorn production-server run).

### 7. Production Deployment (`wsgi.py`, `Procfile`, `DEPLOYMENT.md`, `/production-readiness`)
Adds a real WSGI entry point (`wsgi.py`), a `Procfile` for
Heroku/Render-style platforms, and `DEPLOYMENT.md` covering install →
configure → init DB → seed → run → test → run under gunicorn/waitress
→ container/PaaS deploy → reliability/security/scalability
considerations → rollback plan. The **Production Readiness page is
also a live subsystem**: `agent/deployment_readiness.py` inspects the
actual running configuration (environment variables, installed
packages, filesystem, git-ignore rules, latest test run) and reports a
real readiness score and checklist — not a hardcoded "ready" claim.

### Database additions
Three new tables: `orchestration_log` (per-step audit trail),
`intelligence_snapshots` (event health history for trend charts), and
`test_runs` (automated test run history) — created automatically by
the same `init_db()` used by M1–M3, in the same
`data/registration.db` file.

### New routes
`/intelligence-engine`, `/executive-dashboard`, `/orchestration` (GET
+ POST), `/testing-center` (GET + POST), `/production-readiness`,
plus JSON APIs `/api/intelligence-engine`, `/api/executive-dashboard`,
`/api/orchestration/runs`, `/api/testing-center/latest`,
`/api/production-readiness`.

### New templates
`executive_dashboard.html`, `intelligence_engine.html`,
`orchestration.html`, `testing_center.html`,
`production_readiness.html`, `error.html` — same dark dashboard design
system and sidebar as M1–M3. All five Milestone 4 subtopics
(Intelligence Engine, Executive Dashboard, Agent Orchestration,
End-to-End Testing, Production Deployment) are individually listed and
directly clickable under the "Milestone 4 (Current)" sidebar section —
none are hidden or reachable only indirectly.

---

## Full Route Map (M1–M4, 31 total)

| Milestone | Routes |
|---|---|
| M1 | `/`, `/dashboard`, `/register`, `/attendees`, `/attendees/export.csv`, `/analytics`, `/checkin`, `/notifications` |
| M2 | `/sessions`, `/venues`, `/venue-agent`, `/speaker-agent`, `/speaker-schedule`, `/session-analytics` |
| M3 | `/sponsorship-agent`, `/sponsor-performance`, `/incident-agent`, `/alerts`, `/milestone3-dashboard` |
| M4 | `/intelligence-engine`, `/executive-dashboard`, `/orchestration`, `/testing-center`, `/production-readiness` |
| APIs | `/api/stats`, `/api/session-analytics`, `/api/milestone3-dashboard`, `/api/intelligence-engine`, `/api/executive-dashboard`, `/api/orchestration/runs`, `/api/testing-center/latest`, `/api/production-readiness` |

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env                 # optional; sane defaults without it
python -c "import database; database.init_db()"
python seed_data.py
python app.py                         # http://127.0.0.1:5000
python -m pytest tests/test_milestone4.py -v
```

See `DEPLOYMENT.md` for production (gunicorn/waitress) instructions.
