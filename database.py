"""
database.py
-----------
Handles SQLite database connection, schema creation, and low-level
data access for the Registration Intelligence and Attendee Management
system. This module represents the "Integrate Registration System"
sub-module: it is the single shared data layer that every other
module (agent, analytics, check-in tracker, dashboard, notifications)
reads from and writes to, so all modules stay in sync automatically.

Schema changes made for the enhancement release are applied through
`_ensure_columns()` / `_ensure_tables()` so existing databases created
by earlier versions of this project keep working without losing data.
"""

import sqlite3
import os
from datetime import datetime, date, timedelta

DB_PATH = os.environ.get("DATABASE_PATH") or os.path.join(
    os.path.dirname(__file__), "data", "registration.db")

AGE_GROUPS = [
    ("Under 18", 0, 17),
    ("18-25", 18, 25),
    ("26-35", 26, 35),
    ("36-45", 36, 45),
    ("46-60", 46, 60),
    ("60+", 61, 200),
]

DEFAULT_EVENTS = [
    # name, date (YYYY-MM-DD), time (HH:MM), venue, description
    ("AI Workshop", "2026-08-05", "10:00", "Auditorium A",
     "Hands-on workshop covering practical machine learning and AI tooling."),
    ("Cloud Computing Summit", "2026-08-10", "09:30", "Conference Hall",
     "A summit exploring modern cloud architecture and DevOps practices."),
    ("Full Stack Hackathon", "2026-08-15", "09:00", "Innovation Lab",
     "24-hour hackathon for building full-stack web applications."),
    ("Data Science Meetup", "2026-08-20", "14:00", "Seminar Hall",
     "Community meetup on data science, analytics and visualization."),
    ("Cyber Security Bootcamp", "2026-08-25", "11:00", "Auditorium B",
     "Intensive bootcamp on application and network security fundamentals."),
]

# ---------------------------------------------------------------------
# Milestone 2 default demo data — Venues & Speakers
# (Sessions/bookings/assignments are seeded from seed_data.py instead,
# since they depend on runtime-generated IDs.)
# ---------------------------------------------------------------------
DEFAULT_VENUES = [
    # name, capacity, location, facilities (comma-separated), cost_per_hour
    ("Seminar Hall 1", 80, "Block A - Ground Floor", "Projector,Mic,Whiteboard", 500),
    ("Seminar Hall 2", 150, "Block A - First Floor", "Projector,Mic,AC,WiFi", 900),
    ("Auditorium A", 200, "Block B - Ground Floor", "Projector,Mic,AC,WiFi,Stage Lighting", 1500),
    ("Auditorium B", 300, "Block B - First Floor", "Projector,Mic,AC,WiFi,Stage Lighting,Recording", 2200),
    ("Conference Hall", 120, "Block C - Second Floor", "Projector,Mic,AC,WiFi,Video Conferencing", 1100),
    ("Innovation Lab", 60, "Block D - Third Floor", "Projector,WiFi,Whiteboard,Power Outlets", 400),
    ("Grand Convention Center", 500, "Main Campus", "Projector,Mic,AC,WiFi,Stage Lighting,Recording,Catering Area", 3500),
]

DEFAULT_SPEAKERS = [
    # name, email, bio, experience_years, rating, sessions_count, expertise (list)
    ("Dr. Anitha Raghavan", "anitha.raghavan@example.com",
     "AI researcher and professor specializing in machine learning systems.",
     12, 4.7, 18, ["Artificial Intelligence", "Machine Learning", "Deep Learning", "Python"]),
    ("Mr. Rohan Mehta", "rohan.mehta@example.com",
     "Cloud architect with experience building large-scale distributed systems.",
     9, 4.5, 14, ["Cloud Computing", "DevOps", "Kubernetes", "AWS"]),
    ("Ms. Kavya Subramaniam", "kavya.subramaniam@example.com",
     "Full-stack engineer and hackathon mentor passionate about web platforms.",
     6, 4.6, 10, ["Full Stack Development", "React", "Node.js", "Web Development"]),
    ("Dr. Sanjay Iyer", "sanjay.iyer@example.com",
     "Data scientist focused on analytics, visualization and applied statistics.",
     10, 4.8, 16, ["Data Science", "Data Analytics", "Data Visualization", "Machine Learning"]),
    ("Ms. Fatima Sheikh", "fatima.sheikh@example.com",
     "Cybersecurity consultant specializing in application and network security.",
     8, 4.4, 11, ["Cyber Security", "Network Security", "Ethical Hacking"]),
    ("Mr. Arjun Nair", "arjun.nair@example.com",
     "Product-minded software engineer and frequent conference speaker.",
     7, 4.3, 9, ["Product Management", "Agile", "Full Stack Development"]),
]


# ---------------------------------------------------------------------
# Milestone 3 default demo data — Sponsors, Deliverables, Incidents
# ---------------------------------------------------------------------
DEFAULT_SPONSORS = [
    # name, package, contact_person, contact_email, contract_status,
    # payment_status, payment_amount, branding_status,
    # engagement_pct, booth_visits, leads_generated, session_participation,
    # social_engagement_pct, satisfaction_score, conversion_rate
    ("NexCorp Technologies", "Platinum", "Sanjay Gupta", "partnerships@nexcorp.com",
     "Signed", "Paid", 500000, "Delivered",
     92, 640, 450, 4, 88, 4.8, 34.0),
    ("CloudPeak Solutions", "Gold", "Farhan Ahmed", "sponsorship@cloudpeak.io",
     "Signed", "Paid", 300000, "Delivered",
     84, 410, 280, 3, 74, 4.5, 27.5),
    ("Zenith Solutions Pvt Ltd", "Gold", "Arjun Iyer", "events@zenithsolutions.com",
     "Signed", "Partial", 300000, "In Progress",
     76, 360, 240, 2, 66, 4.2, 24.0),
    ("Bright Systems Inc", "Silver", "Sneha Kulkarni", "marketing@brightsys.com",
     "Signed", "Paid", 150000, "In Progress",
     68, 220, 150, 2, 55, 4.0, 20.5),
    ("SpeakerHub Global", "Silver", "Aditi Rao", "partners@speakerhub.com",
     "Under Negotiation", "Pending", 150000, "Pending",
     52, 140, 95, 1, 40, 3.6, 15.0),
    ("PSG Institute of Management", "Bronze", "Lakshmi Venkat", "outreach@psgim.edu",
     "Signed", "Paid", 60000, "Delivered",
     71, 130, 88, 1, 48, 4.1, 19.0),
    ("Infosys Technologies", "Platinum", "Rahul Verma", "csr@infosys.com",
     "Signed", "Partial", 500000, "In Progress",
     48, 190, 120, 2, 38, 3.4, 12.5),
    ("Kumaraguru College Foundation", "Bronze", "Divya Prakash", "foundation@kct.ac.in",
     "Pending", "Pending", 60000, "Pending",
     35, 60, 40, 0, 22, 3.1, 8.0),
]

# sponsor_name -> list of (deliverable, category, due_date, status)
DEFAULT_DELIVERABLES = {
    "NexCorp Technologies": [
        ("Logo on main stage backdrop", "Branding", "2026-08-04", "Completed"),
        ("Platinum booth setup (Hall A)", "Logistics", "2026-08-05", "Completed"),
        ("Dedicated keynote slot", "Marketing", "2026-08-05", "Completed"),
    ],
    "CloudPeak Solutions": [
        ("Logo on event website", "Digital", "2026-08-02", "Completed"),
        ("Social media shout-out (3 posts)", "Digital", "2026-08-08", "In Progress"),
        ("Booth setup (Hall B)", "Logistics", "2026-08-10", "Completed"),
    ],
    "Zenith Solutions Pvt Ltd": [
        ("Banner placement — main lobby", "Branding", "2026-08-06", "Completed"),
        ("Product demo slot", "Marketing", "2026-08-12", "Pending"),
    ],
    "Bright Systems Inc": [
        ("Logo on attendee badges", "Branding", "2026-08-01", "Completed"),
        ("Newsletter mention", "Marketing", "2026-08-14", "Pending"),
    ],
    "SpeakerHub Global": [
        ("Contract signature", "Logistics", "2026-08-01", "Pending"),
        ("Booth space confirmation", "Logistics", "2026-08-15", "Pending"),
    ],
    "PSG Institute of Management": [
        ("Logo on schedule handouts", "Branding", "2026-08-07", "Completed"),
    ],
    "Infosys Technologies": [
        ("Platinum booth setup (Hall A)", "Logistics", "2026-08-05", "In Progress"),
        ("CSR panel mention", "Marketing", "2026-08-18", "Pending"),
        ("Social media shout-out (5 posts)", "Digital", "2026-08-20", "Pending"),
    ],
    "Kumaraguru College Foundation": [
        ("Contract signature", "Logistics", "2026-08-22", "Pending"),
    ],
}

# title, category, description, affected_area, status, reported_at (relative days offset), reported_by
DEFAULT_INCIDENTS = [
    ("Main generator failure during keynote", "Power Failure",
     "The main power generator tripped while the keynote was in progress, cutting stage lighting and sound.",
     "Auditorium A", "Resolved", -6, "Operations Team"),
    ("Smoke detected near catering area", "Fire-Related Issue",
     "A minor smoke alert was triggered near the catering counters; fire wardens are investigating now.",
     "Catering Area", "Open", -2, "Prethie K"),
    ("Attendee collapsed near registration desk", "Medical Emergency",
     "An attendee felt dizzy and collapsed near the registration desk; on-site medical staff responded.",
     "Registration Desk", "Resolved", -4, "Prethie K"),
    ("Unauthorized entry attempt at VIP gate", "Security Issue",
     "A visitor without valid credentials attempted to enter the VIP gate; security intervened.",
     "VIP Gate", "Resolved", -4, "Security Team"),
    ("Keynote speaker cancelled last minute", "Speaker Cancellation",
     "Dr. Anitha Raghavan reported a travel delay and may not make the 10:00 AM keynote slot.",
     "Auditorium A", "In Progress", -1, "Prethie K"),
    ("Registration system slow / timing out", "Registration System Failure",
     "The online registration portal is responding slowly, causing long queues at the check-in desk.",
     "Registration Desk", "In Progress", -1, "IT Team"),
    ("WiFi outage in Conference Hall", "Network Outage",
     "Conference Hall WiFi has been down for 20 minutes, affecting live-streamed sessions.",
     "Conference Hall", "Open", 0, "IT Team"),
    ("Microphone not working in Hall A", "Audio/Video Failure",
     "The handheld microphone in Hall A stopped working; the next session starts in 10 minutes.",
     "Hall A", "Open", 0, "Prethie K"),
    ("Overcrowding at Auditorium B entrance", "Overcrowding",
     "Attendee count at Auditorium B has exceeded the comfortable entry flow; a queue has formed outside.",
     "Auditorium B", "Open", 0, "Venue Team"),
    ("Projector missing for Data Science session", "Missing Equipment",
     "The spare projector reserved for Seminar Hall 1 could not be located in the equipment store.",
     "Seminar Hall 1", "Open", 0, "Logistics Team"),
    ("Session running 20 minutes behind schedule", "Session Delay",
     "The Cloud Architecture Patterns session overran and is delaying the next scheduled session.",
     "Auditorium B", "In Progress", 0, "Program Team"),
    ("Projector screen flickering in Innovation Lab", "Venue Technical Failure",
     "The projection screen in the Innovation Lab is flickering intermittently during the hackathon briefing.",
     "Innovation Lab", "Open", 0, "Prethie K"),
]


def get_connection():
    """Return a SQLite connection with row access by column name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _existing_columns(conn, table):
    cur = conn.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}


def _ensure_columns(conn, table, columns):
    """columns: dict of {column_name: 'SQL TYPE [DEFAULT ...]'}. Adds any
    missing column without touching existing data (safe migration)."""
    existing = _existing_columns(conn, table)
    for col, ddl in columns.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")


def init_db():
    """Create tables if they do not already exist, migrate older
    databases to the current schema, and seed default events."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS attendees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reg_code TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            organization TEXT,
            category TEXT NOT NULL,
            source TEXT DEFAULT 'Agent',
            risk_flag TEXT DEFAULT 'Low',
            registered_at TEXT NOT NULL,
            checked_in INTEGER DEFAULT 0,
            checked_in_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS agent_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attendee_id INTEGER,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (attendee_id) REFERENCES attendees(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            event_date TEXT NOT NULL,
            event_time TEXT NOT NULL,
            venue TEXT,
            description TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS notification_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attendee_id INTEGER,
            notif_type TEXT NOT NULL,
            success INTEGER NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (attendee_id) REFERENCES attendees(id)
        )
    """)

    # ===================================================================
    # Milestone 2 — Agentic AI for Smart Event Management Operations
    # (functional areas: Venue Agent, Speaker Agent, Session Analytics)
    # These tables extend the same shared database used by Milestone 1;
    # nothing above this block was changed.
    # ===================================================================
    cur.execute("""
        CREATE TABLE IF NOT EXISTS venues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            capacity INTEGER NOT NULL,
            location TEXT,
            facilities TEXT,
            cost_per_hour REAL DEFAULT 0,
            status TEXT DEFAULT 'Active'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS venue_bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venue_id INTEGER NOT NULL,
            session_id INTEGER,
            label TEXT,
            booking_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            attendees INTEGER,
            booked_by TEXT,
            status TEXT DEFAULT 'Booked',
            created_at TEXT NOT NULL,
            FOREIGN KEY (venue_id) REFERENCES venues(id),
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS speakers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            email TEXT,
            bio TEXT,
            experience_years INTEGER DEFAULT 0,
            rating REAL DEFAULT 0,
            sessions_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Active'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS speaker_expertise (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            speaker_id INTEGER NOT NULL,
            topic TEXT NOT NULL,
            source TEXT DEFAULT 'Profile',
            added_at TEXT NOT NULL,
            FOREIGN KEY (speaker_id) REFERENCES speakers(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            topic TEXT NOT NULL,
            event_name TEXT,
            session_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            attendees_expected INTEGER DEFAULT 0,
            facilities_required TEXT,
            preferred_location TEXT,
            venue_id INTEGER,
            speaker_id INTEGER,
            status TEXT DEFAULT 'Draft',
            created_at TEXT NOT NULL,
            FOREIGN KEY (venue_id) REFERENCES venues(id),
            FOREIGN KEY (speaker_id) REFERENCES speakers(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS speaker_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            speaker_id INTEGER NOT NULL,
            match_score REAL,
            reasons TEXT,
            assigned_at TEXT NOT NULL,
            status TEXT DEFAULT 'Confirmed',
            FOREIGN KEY (session_id) REFERENCES sessions(id),
            FOREIGN KEY (speaker_id) REFERENCES speakers(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS session_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER UNIQUE NOT NULL,
            attendees_registered INTEGER DEFAULT 0,
            attendees_present INTEGER DEFAULT 0,
            avg_rating REAL DEFAULT 0,
            feedback_count INTEGER DEFAULT 0,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)

    # ===================================================================
    # Milestone 3 — Sponsorship & Incident Management
    # (functional areas: Sponsorship Agent, Incident Agent, Alert System,
    # Sponsor Performance Tracking). These tables extend the same shared
    # database used by Milestone 1 and Milestone 2; nothing above this
    # block was changed.
    # ===================================================================
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sponsors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            package TEXT DEFAULT 'Bronze',
            contact_person TEXT,
            contact_email TEXT,
            contract_status TEXT DEFAULT 'Pending',
            payment_status TEXT DEFAULT 'Pending',
            payment_amount REAL DEFAULT 0,
            branding_status TEXT DEFAULT 'Pending',
            engagement_pct REAL DEFAULT 0,
            booth_visits INTEGER DEFAULT 0,
            leads_generated INTEGER DEFAULT 0,
            session_participation INTEGER DEFAULT 0,
            social_engagement_pct REAL DEFAULT 0,
            satisfaction_score REAL DEFAULT 0,
            conversion_rate REAL DEFAULT 0,
            status TEXT DEFAULT 'Active',
            added_by TEXT DEFAULT 'Prethie K',
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sponsor_deliverables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sponsor_id INTEGER NOT NULL,
            deliverable TEXT NOT NULL,
            category TEXT DEFAULT 'General',
            due_date TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TEXT NOT NULL,
            FOREIGN KEY (sponsor_id) REFERENCES sponsors(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            category TEXT NOT NULL,
            severity TEXT DEFAULT 'Medium',
            priority TEXT DEFAULT 'Medium',
            affected_area TEXT,
            responsible_team TEXT,
            recommended_action TEXT,
            alert_type TEXT DEFAULT 'Medium',
            status TEXT DEFAULT 'Open',
            reported_by TEXT DEFAULT 'Prethie K',
            reported_at TEXT NOT NULL,
            resolved_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type TEXT NOT NULL,
            category TEXT DEFAULT 'System',
            title TEXT NOT NULL,
            description TEXT,
            recommended_action TEXT,
            status TEXT DEFAULT 'Active',
            related_incident_id INTEGER,
            related_sponsor_id INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (related_incident_id) REFERENCES incidents(id),
            FOREIGN KEY (related_sponsor_id) REFERENCES sponsors(id)
        )
    """)

    # =====================================================================
    # MILESTONE 4 -- Event Intelligence & Enterprise Deployment
    # Two new tables only. Nothing above this block is touched: M1, M2
    # and M3 tables, columns and data are untouched by Milestone 4.
    # =====================================================================
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orchestration_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            workflow_name TEXT NOT NULL,
            step_number INTEGER NOT NULL,
            agent_name TEXT NOT NULL,
            action TEXT NOT NULL,
            input_summary TEXT,
            output_summary TEXT,
            status TEXT DEFAULT 'Success',
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS test_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            total INTEGER NOT NULL,
            passed INTEGER NOT NULL,
            failed INTEGER NOT NULL,
            errors INTEGER NOT NULL,
            duration_seconds REAL,
            category_json TEXT,
            raw_output TEXT,
            triggered_by TEXT DEFAULT 'Manual',
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS intelligence_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_health_score REAL NOT NULL,
            event_health_label TEXT NOT NULL,
            risks_json TEXT,
            recommendations_json TEXT,
            kpi_json TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # --- Migration-safe column additions for the enhancement release ---
    _ensure_columns(conn, "attendees", {
        "age": "INTEGER",
        "gender": "TEXT",
        "city": "TEXT",
        "event": "TEXT",
        "qr_path": "TEXT",
        "confirmation_sent": "INTEGER DEFAULT 0",
        "reminder_3d_sent": "INTEGER DEFAULT 0",
        "reminder_1d_sent": "INTEGER DEFAULT 0",
        "reminder_0d_sent": "INTEGER DEFAULT 0",
    })

    conn.commit()

    # Seed default events only if the table is empty (first run) so we
    # never overwrite events an organizer may have customized.
    cur.execute("SELECT COUNT(*) AS c FROM events")
    if cur.fetchone()["c"] == 0:
        cur.executemany(
            "INSERT INTO events (name, event_date, event_time, venue, description) "
            "VALUES (?, ?, ?, ?, ?)",
            DEFAULT_EVENTS,
        )
        conn.commit()

    # Seed default venues (Milestone 2) only on first run.
    cur.execute("SELECT COUNT(*) AS c FROM venues")
    if cur.fetchone()["c"] == 0:
        cur.executemany(
            "INSERT INTO venues (name, capacity, location, facilities, cost_per_hour) "
            "VALUES (?, ?, ?, ?, ?)",
            DEFAULT_VENUES,
        )
        conn.commit()

    # Seed default speakers + their expertise topics (Milestone 2) only on first run.
    cur.execute("SELECT COUNT(*) AS c FROM speakers")
    if cur.fetchone()["c"] == 0:
        now = datetime.now().isoformat(timespec="seconds")
        for name, email, bio, exp_years, rating, sessions_count, expertise in DEFAULT_SPEAKERS:
            cur.execute(
                "INSERT INTO speakers (name, email, bio, experience_years, rating, sessions_count) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (name, email, bio, exp_years, rating, sessions_count),
            )
            speaker_id = cur.lastrowid
            for topic in expertise:
                cur.execute(
                    "INSERT INTO speaker_expertise (speaker_id, topic, source, added_at) "
                    "VALUES (?, ?, 'Profile', ?)",
                    (speaker_id, topic, now),
                )
        conn.commit()

    # Seed default sponsors + deliverables (Milestone 3) only on first run.
    cur.execute("SELECT COUNT(*) AS c FROM sponsors")
    if cur.fetchone()["c"] == 0:
        now = datetime.now().isoformat(timespec="seconds")
        for (name, package, contact_person, contact_email, contract_status,
             payment_status, payment_amount, branding_status, engagement_pct,
             booth_visits, leads_generated, session_participation,
             social_engagement_pct, satisfaction_score, conversion_rate) in DEFAULT_SPONSORS:
            cur.execute("""
                INSERT INTO sponsors
                    (name, package, contact_person, contact_email, contract_status,
                     payment_status, payment_amount, branding_status, engagement_pct,
                     booth_visits, leads_generated, session_participation,
                     social_engagement_pct, satisfaction_score, conversion_rate,
                     status, added_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active', 'Prethie K', ?)
            """, (name, package, contact_person, contact_email, contract_status,
                  payment_status, payment_amount, branding_status, engagement_pct,
                  booth_visits, leads_generated, session_participation,
                  social_engagement_pct, satisfaction_score, conversion_rate, now))
            sponsor_id = cur.lastrowid
            for deliverable, category, due_date, status in DEFAULT_DELIVERABLES.get(name, []):
                cur.execute("""
                    INSERT INTO sponsor_deliverables
                        (sponsor_id, deliverable, category, due_date, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (sponsor_id, deliverable, category, due_date, status, now))
        conn.commit()

    # Seed default incidents (Milestone 3) only on first run. Each incident
    # is run through the real Incident Agent classification logic so the
    # seeded severity/priority/team/action match what a live submission
    # would produce.
    cur.execute("SELECT COUNT(*) AS c FROM incidents")
    if cur.fetchone()["c"] == 0:
        from agent import incident_agent as _incident_agent
        base_now = datetime.now()
        for (title, category, description, affected_area, status,
             day_offset, reported_by) in DEFAULT_INCIDENTS:
            classification = _incident_agent.classify_incident(category, description)
            reported_at = (base_now + timedelta(days=day_offset)).isoformat(timespec="seconds")
            resolved_at = None
            if status == "Resolved":
                resolved_at = (base_now + timedelta(days=day_offset, hours=3)).isoformat(timespec="seconds")
            cur.execute("""
                INSERT INTO incidents
                    (title, description, category, severity, priority, affected_area,
                     responsible_team, recommended_action, alert_type, status,
                     reported_by, reported_at, resolved_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (title, description, category, classification["severity"],
                  classification["priority"], affected_area, classification["responsible_team"],
                  classification["recommended_action"], classification["alert_type"], status,
                  reported_by, reported_at, resolved_at))
            incident_id = cur.lastrowid

            alert_status = "Resolved" if status == "Resolved" else "Active"
            cur.execute("""
                INSERT INTO alerts
                    (alert_type, category, title, description, recommended_action,
                     status, related_incident_id, created_at)
                VALUES (?, 'Incident', ?, ?, ?, ?, ?, ?)
            """, (classification["alert_type"], f"{category}: {title}", description,
                  classification["recommended_action"], alert_status, incident_id, reported_at))
        conn.commit()

        # A handful of standalone informational / sponsor alerts so the
        # Alert Center shows every alert type immediately (not only
        # incident-derived ones).
        info_alerts = [
            ("Informational", "Sponsor", "Sponsor deliverable completed",
             "NexCorp Technologies completed their platinum booth setup ahead of schedule.",
             "No action required.", -3),
            ("Informational", "Schedule", "Session completed",
             "Introduction to Machine Learning concluded with 91% attendance.", "No action required.", -2),
            ("Informational", "Sponsor", "Speaker arrival confirmed",
             "Dr. Sanjay Iyer has checked in and confirmed his session slot.", "No action required.", -1),
            ("Medium", "Sponsor", "Low sponsor engagement detected",
             "SpeakerHub Global's engagement score has dropped below the 60% healthy threshold.",
             "Schedule a check-in call and offer additional promotional support.", 0),
            ("Medium", "Sponsor", "Pending deliverable approaching due date",
             "Zenith Solutions Pvt Ltd has a product demo slot deliverable due soon.",
             "Confirm demo logistics with the sponsor contact.", 0),
        ]
        for alert_type, category, title, description, action, day_offset in info_alerts:
            created_at = (base_now + timedelta(days=day_offset)).isoformat(timespec="seconds")
            cur.execute("""
                INSERT INTO alerts
                    (alert_type, category, title, description, recommended_action, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'Active', ?)
            """, (alert_type, category, title, description, action, created_at))
        conn.commit()

    conn.close()


# ---------------------------------------------------------------------
# Attendees
# ---------------------------------------------------------------------
def insert_attendee(record: dict) -> int:
    record.setdefault("age", None)
    record.setdefault("gender", None)
    record.setdefault("city", None)
    record.setdefault("event", None)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO attendees
            (reg_code, full_name, email, phone, organization, category,
             age, gender, city, event,
             source, risk_flag, registered_at, checked_in, checked_in_at)
        VALUES (:reg_code, :full_name, :email, :phone, :organization,
                :category, :age, :gender, :city, :event,
                :source, :risk_flag, :registered_at, 0, NULL)
    """, record)
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def set_qr_path(attendee_id, qr_path):
    conn = get_connection()
    conn.execute("UPDATE attendees SET qr_path = ? WHERE id = ?", (qr_path, attendee_id))
    conn.commit()
    conn.close()


def log_agent_message(attendee_id, message):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO agent_log (attendee_id, message, created_at) VALUES (?, ?, ?)",
        (attendee_id, message, datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()
    conn.close()


SORTABLE_COLUMNS = {
    "name": "full_name",
    "email": "email",
    "age": "age",
    "city": "city",
    "event": "event",
    "registered_at": "registered_at",
    "checked_in": "checked_in",
    "category": "category",
}


def get_all_attendees(search=None, category=None, checked_in=None, event=None,
                       gender=None, sort_by=None, sort_dir="desc",
                       limit=None, offset=0):
    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT * FROM attendees WHERE 1=1"
    params = []
    if search:
        query += " AND (full_name LIKE ? OR email LIKE ? OR reg_code LIKE ? OR phone LIKE ?)"
        like = f"%{search}%"
        params += [like, like, like, like]
    if category and category != "All":
        query += " AND category = ?"
        params.append(category)
    if event and event != "All":
        query += " AND event = ?"
        params.append(event)
    if gender and gender != "All":
        query += " AND gender = ?"
        params.append(gender)
    if checked_in in ("0", "1"):
        query += " AND checked_in = ?"
        params.append(int(checked_in))

    column = SORTABLE_COLUMNS.get(sort_by, "registered_at")
    direction = "ASC" if str(sort_dir).lower() == "asc" else "DESC"
    query += f" ORDER BY {column} {direction}"

    if limit is not None:
        query += " LIMIT ? OFFSET ?"
        params += [limit, offset]

    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def count_attendees(search=None, category=None, checked_in=None, event=None, gender=None):
    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT COUNT(*) AS c FROM attendees WHERE 1=1"
    params = []
    if search:
        query += " AND (full_name LIKE ? OR email LIKE ? OR reg_code LIKE ? OR phone LIKE ?)"
        like = f"%{search}%"
        params += [like, like, like, like]
    if category and category != "All":
        query += " AND category = ?"
        params.append(category)
    if event and event != "All":
        query += " AND event = ?"
        params.append(event)
    if gender and gender != "All":
        query += " AND gender = ?"
        params.append(gender)
    if checked_in in ("0", "1"):
        query += " AND checked_in = ?"
        params.append(int(checked_in))
    cur.execute(query, params)
    total = cur.fetchone()["c"]
    conn.close()
    return total


def get_attendee_by_code(reg_code):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM attendees WHERE reg_code = ?", (reg_code,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_attendee_by_email(email):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM attendees WHERE email = ?", (email,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def mark_checked_in(reg_code):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE attendees SET checked_in = 1, checked_in_at = ? WHERE reg_code = ?",
        (datetime.now().isoformat(timespec="seconds"), reg_code)
    )
    conn.commit()
    affected = cur.rowcount
    conn.close()
    return affected > 0


def get_recent_agent_logs(limit=15):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT agent_log.message, agent_log.created_at, attendees.full_name
        FROM agent_log
        LEFT JOIN attendees ON attendees.id = agent_log.attendee_id
        ORDER BY agent_log.id DESC LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ---------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------
def get_all_events():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM events ORDER BY event_date ASC, event_time ASC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_event_by_name(name):
    if not name:
        return None
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM events WHERE name = ?", (name,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_next_upcoming_event():
    """Soonest event (date+time) that has not started yet."""
    now = datetime.now()
    events = get_all_events()
    upcoming = []
    for ev in events:
        try:
            dt = datetime.strptime(f"{ev['event_date']} {ev['event_time']}", "%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            continue
        if dt >= now:
            ev["_datetime"] = dt
            upcoming.append(ev)
    if not upcoming:
        return None
    upcoming.sort(key=lambda e: e["_datetime"])
    best = upcoming[0]
    del best["_datetime"]
    return best


# ---------------------------------------------------------------------
# Notification log (Event Notification & Reminder System)
# ---------------------------------------------------------------------
def log_notification(attendee_id, notif_type, success, note):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO notification_log (attendee_id, notif_type, success, note, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (attendee_id, notif_type, 1 if success else 0, note,
          datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()


def mark_reminder_sent(attendee_id, label):
    column = {"3d": "reminder_3d_sent", "1d": "reminder_1d_sent", "0d": "reminder_0d_sent"}.get(label)
    if not column:
        return
    conn = get_connection()
    conn.execute(f"UPDATE attendees SET {column} = 1 WHERE id = ?", (attendee_id,))
    conn.commit()
    conn.close()


def get_notification_log(limit=25):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT notification_log.*, attendees.full_name, attendees.reg_code
        FROM notification_log
        LEFT JOIN attendees ON attendees.id = notification_log.attendee_id
        ORDER BY notification_log.id DESC LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ---------------------------------------------------------------------
# Stats / Analytics
# ---------------------------------------------------------------------
def get_stats():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS c FROM attendees")
    total = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) AS c FROM attendees WHERE checked_in = 1")
    checked_in = cur.fetchone()["c"]

    today_str = date.today().isoformat()
    cur.execute("SELECT COUNT(*) AS c FROM attendees WHERE substr(registered_at, 1, 10) = ?", (today_str,))
    today_count = cur.fetchone()["c"]

    cur.execute("SELECT AVG(age) AS a FROM attendees WHERE age IS NOT NULL")
    avg_age_row = cur.fetchone()["a"]
    avg_age = round(avg_age_row, 1) if avg_age_row else 0

    cur.execute("SELECT category, COUNT(*) AS c FROM attendees GROUP BY category")
    by_category = {r["category"]: r["c"] for r in cur.fetchall()}

    cur.execute("SELECT source, COUNT(*) AS c FROM attendees GROUP BY source")
    by_source = {r["source"]: r["c"] for r in cur.fetchall()}

    cur.execute("SELECT risk_flag, COUNT(*) AS c FROM attendees GROUP BY risk_flag")
    by_risk = {r["risk_flag"]: r["c"] for r in cur.fetchall()}

    cur.execute("""
        SELECT COALESCE(NULLIF(TRIM(gender), ''), 'Not specified') AS g, COUNT(*) AS c
        FROM attendees GROUP BY g
    """)
    by_gender = {r["g"]: r["c"] for r in cur.fetchall()}

    cur.execute("""
        SELECT COALESCE(NULLIF(TRIM(city), ''), 'Not specified') AS city, COUNT(*) AS c
        FROM attendees GROUP BY city ORDER BY c DESC LIMIT 10
    """)
    by_city = {r["city"]: r["c"] for r in cur.fetchall()}

    cur.execute("""
        SELECT COALESCE(NULLIF(TRIM(event), ''), 'Not specified') AS event, COUNT(*) AS c
        FROM attendees GROUP BY event ORDER BY c DESC
    """)
    by_event = {r["event"]: r["c"] for r in cur.fetchall()}

    cur.execute("""
        SELECT substr(registered_at, 1, 10) AS day, COUNT(*) AS c
        FROM attendees GROUP BY day ORDER BY day
    """)
    by_day = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT age FROM attendees WHERE age IS NOT NULL")
    ages = [r["age"] for r in cur.fetchall()]
    age_groups = {label: 0 for label, _, _ in AGE_GROUPS}
    for a in ages:
        for label, lo, hi in AGE_GROUPS:
            if lo <= a <= hi:
                age_groups[label] += 1
                break

    conn.close()
    return {
        "total": total,
        "checked_in": checked_in,
        "not_checked_in": total - checked_in,
        "today_count": today_count,
        "avg_age": avg_age,
        "checkin_pct": round((checked_in / total) * 100, 1) if total else 0,
        "by_category": by_category,
        "by_source": by_source,
        "by_risk": by_risk,
        "by_gender": by_gender,
        "by_city": by_city,
        "by_event": by_event,
        "by_day": by_day,
        "age_groups": age_groups,
    }


# =======================================================================
# MILESTONE 2 — Agentic AI for Smart Event Management Operations
# (functional areas: Venue Agent, Speaker Agent, Session Analytics)
# =======================================================================
#
# Everything below builds on the same shared SQLite database used by
# Milestone 1 (attendees / events / agent_log / notification_log are
# untouched). The new tables — venues, venue_bookings, speakers,
# speaker_expertise, sessions, speaker_assignments, session_analytics —
# are related to the existing schema through `sessions.event_name`
# (which matches Milestone 1's `events.name`) and are used by the
# Venue Agent, Speaker Agent, Session Analytics and Final Event
# Schedule modules implemented in venue_agent.py / speaker_agent.py /
# app.py.

# -----------------------------------------------------------------
# Venues
# -----------------------------------------------------------------
def get_all_venues(status="Active"):
    conn = get_connection()
    cur = conn.cursor()
    if status:
        cur.execute("SELECT * FROM venues WHERE status = ? ORDER BY capacity ASC", (status,))
    else:
        cur.execute("SELECT * FROM venues ORDER BY capacity ASC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_venue(venue_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM venues WHERE id = ?", (venue_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def _times_overlap(start_a, end_a, start_b, end_b):
    """HH:MM strings compare correctly lexicographically."""
    return start_a < end_b and start_b < end_a


def get_venue_bookings(venue_id=None, booking_date=None, status="Booked"):
    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT * FROM venue_bookings WHERE 1=1"
    params = []
    if venue_id is not None:
        query += " AND venue_id = ?"
        params.append(venue_id)
    if booking_date is not None:
        query += " AND booking_date = ?"
        params.append(booking_date)
    if status is not None:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY booking_date, start_time"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_all_bookings_detailed():
    """All venue bookings joined with venue name/capacity, for the
    Venues management page."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT venue_bookings.*, venues.name AS venue_name, venues.capacity AS venue_capacity
        FROM venue_bookings
        JOIN venues ON venues.id = venue_bookings.venue_id
        ORDER BY venue_bookings.booking_date DESC, venue_bookings.start_time DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def check_venue_availability(venue_id, booking_date, start_time, end_time, exclude_booking_id=None):
    """Returns (is_available: bool, conflicting_booking: dict|None)."""
    bookings = get_venue_bookings(venue_id=venue_id, booking_date=booking_date, status="Booked")
    for b in bookings:
        if exclude_booking_id and b["id"] == exclude_booking_id:
            continue
        if _times_overlap(start_time, end_time, b["start_time"], b["end_time"]):
            return False, b
    return True, None


def create_booking(venue_id, booking_date, start_time, end_time, attendees,
                    booked_by="Organizer", label=None, session_id=None):
    """Books a venue after re-checking for conflicts (prevents double
    booking even under concurrent requests to a reasonable degree for
    a single-process dev server)."""
    available, conflict = check_venue_availability(venue_id, booking_date, start_time, end_time)
    if not available:
        return False, conflict

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO venue_bookings
            (venue_id, session_id, label, booking_date, start_time, end_time,
             attendees, booked_by, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Booked', ?)
    """, (venue_id, session_id, label, booking_date, start_time, end_time,
          attendees, booked_by, datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    booking_id = cur.lastrowid
    conn.close()

    if session_id:
        update_session_venue(session_id, venue_id)

    return True, get_booking(booking_id)


def get_booking(booking_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM venue_bookings WHERE id = ?", (booking_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def cancel_booking(booking_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT session_id FROM venue_bookings WHERE id = ?", (booking_id,))
    row = cur.fetchone()
    cur.execute("UPDATE venue_bookings SET status = 'Cancelled' WHERE id = ?", (booking_id,))
    conn.commit()
    conn.close()
    if row and row["session_id"]:
        update_session_venue(row["session_id"], None)
        update_session_status(row["session_id"], "Draft")
    return True


# -----------------------------------------------------------------
# Speakers
# -----------------------------------------------------------------
def get_all_speakers():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM speakers WHERE status = 'Active' ORDER BY rating DESC")
    speakers = [dict(r) for r in cur.fetchall()]
    conn.close()
    for sp in speakers:
        sp["expertise"] = get_speaker_expertise(sp["id"])
    return speakers


def get_speaker(speaker_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM speakers WHERE id = ?", (speaker_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    speaker = dict(row)
    speaker["expertise"] = get_speaker_expertise(speaker_id)
    return speaker


def get_speaker_expertise(speaker_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT topic, source FROM speaker_expertise WHERE speaker_id = ? ORDER BY id", (speaker_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def add_speaker_expertise(speaker_id, topic, source="Mentioned during session"):
    """Implements the 'intelligent scenario' from the brief: a speaker
    mentions expertise in an additional topic while presenting, and
    that topic becomes searchable for future speaker recommendations."""
    existing = [e["topic"].lower() for e in get_speaker_expertise(speaker_id)]
    if topic.strip().lower() in existing:
        return False
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO speaker_expertise (speaker_id, topic, source, added_at) VALUES (?, ?, ?, ?)",
        (speaker_id, topic.strip(), source, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()
    return True


def get_speaker_schedule(speaker_id):
    """All sessions currently assigned to this speaker (for conflict
    checks and the Speaker Schedule page)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM sessions WHERE speaker_id = ? AND status != 'Cancelled'
        ORDER BY session_date, start_time
    """, (speaker_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def check_speaker_availability(speaker_id, session_date, start_time, end_time, exclude_session_id=None):
    """Returns (is_available: bool, conflicting_session: dict|None)."""
    for s in get_speaker_schedule(speaker_id):
        if exclude_session_id and s["id"] == exclude_session_id:
            continue
        if s["session_date"] == session_date and _times_overlap(start_time, end_time, s["start_time"], s["end_time"]):
            return False, s
    return True, None


def get_all_speaker_assignments():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT sessions.id AS session_id, sessions.title, sessions.topic,
               sessions.session_date, sessions.start_time, sessions.end_time,
               sessions.status AS session_status,
               speakers.id AS speaker_id, speakers.name AS speaker_name,
               speakers.rating AS speaker_rating
        FROM sessions
        JOIN speakers ON speakers.id = sessions.speaker_id
        WHERE sessions.status != 'Cancelled'
        ORDER BY sessions.session_date, sessions.start_time
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def assign_speaker_to_session(session_id, speaker_id, match_score=None, reasons=""):
    """Assigns a speaker to a session after re-checking for scheduling
    conflicts (prevents the same speaker being double-booked)."""
    session = get_session(session_id)
    if not session:
        return False, "Session not found."

    available, conflict = check_speaker_availability(
        speaker_id, session["session_date"], session["start_time"], session["end_time"],
        exclude_session_id=session_id,
    )
    if not available:
        return False, conflict

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO speaker_assignments (session_id, speaker_id, match_score, reasons, assigned_at, status)
        VALUES (?, ?, ?, ?, ?, 'Confirmed')
    """, (session_id, speaker_id, match_score, reasons, datetime.now().isoformat(timespec="seconds")))
    cur.execute("UPDATE speakers SET sessions_count = sessions_count + 1 WHERE id = ?", (speaker_id,))
    conn.commit()
    conn.close()

    update_session_speaker(session_id, speaker_id)
    return True, get_session(session_id)


# -----------------------------------------------------------------
# Sessions
# -----------------------------------------------------------------
def create_session(title, topic, event_name, session_date, start_time, end_time,
                    attendees_expected, facilities_required="", preferred_location=""):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO sessions
            (title, topic, event_name, session_date, start_time, end_time,
             attendees_expected, facilities_required, preferred_location, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Draft', ?)
    """, (title, topic, event_name, session_date, start_time, end_time,
          attendees_expected, facilities_required, preferred_location,
          datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    session_id = cur.lastrowid
    conn.close()
    return get_session(session_id)


def get_all_sessions():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT sessions.*, venues.name AS venue_name, venues.capacity AS venue_capacity,
               speakers.name AS speaker_name
        FROM sessions
        LEFT JOIN venues ON venues.id = sessions.venue_id
        LEFT JOIN speakers ON speakers.id = sessions.speaker_id
        ORDER BY sessions.session_date, sessions.start_time
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_session(session_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT sessions.*, venues.name AS venue_name, venues.capacity AS venue_capacity,
               venues.location AS venue_location, speakers.name AS speaker_name,
               speakers.rating AS speaker_rating
        FROM sessions
        LEFT JOIN venues ON venues.id = sessions.venue_id
        LEFT JOIN speakers ON speakers.id = sessions.speaker_id
        WHERE sessions.id = ?
    """, (session_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def update_session_venue(session_id, venue_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE sessions SET venue_id = ? WHERE id = ?", (venue_id, session_id))
    conn.commit()
    conn.close()
    _refresh_session_status(session_id)


def update_session_speaker(session_id, speaker_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE sessions SET speaker_id = ? WHERE id = ?", (speaker_id, session_id))
    conn.commit()
    conn.close()
    _refresh_session_status(session_id)


def update_session_status(session_id, status):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE sessions SET status = ? WHERE id = ?", (status, session_id))
    conn.commit()
    conn.close()


def _refresh_session_status(session_id):
    session = get_session(session_id)
    if not session:
        return
    if session["venue_id"] and session["speaker_id"]:
        update_session_status(session_id, "Confirmed")
    elif session["venue_id"]:
        update_session_status(session_id, "Venue Booked")
    elif session["speaker_id"]:
        update_session_status(session_id, "Speaker Assigned")
    else:
        update_session_status(session_id, "Draft")


# -----------------------------------------------------------------
# Session Analytics
# -----------------------------------------------------------------
def upsert_session_analytics(session_id, attendees_registered, attendees_present,
                              avg_rating, feedback_count):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM session_analytics WHERE session_id = ?", (session_id,))
    exists = cur.fetchone()
    now = datetime.now().isoformat(timespec="seconds")
    if exists:
        cur.execute("""
            UPDATE session_analytics
            SET attendees_registered = ?, attendees_present = ?, avg_rating = ?,
                feedback_count = ?, updated_at = ?
            WHERE session_id = ?
        """, (attendees_registered, attendees_present, avg_rating, feedback_count, now, session_id))
    else:
        cur.execute("""
            INSERT INTO session_analytics
                (session_id, attendees_registered, attendees_present, avg_rating, feedback_count, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (session_id, attendees_registered, attendees_present, avg_rating, feedback_count, now))
    conn.commit()
    conn.close()


def get_session_analytics_all():
    """Every session joined with its analytics row (if any), venue and
    speaker — the core dataset for the Session Analytics page."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT sessions.id AS session_id, sessions.title, sessions.topic,
               sessions.session_date, sessions.start_time, sessions.end_time,
               sessions.status,
               venues.name AS venue_name, venues.capacity AS venue_capacity,
               speakers.name AS speaker_name,
               session_analytics.attendees_registered, session_analytics.attendees_present,
               session_analytics.avg_rating, session_analytics.feedback_count
        FROM sessions
        LEFT JOIN venues ON venues.id = sessions.venue_id
        LEFT JOIN speakers ON speakers.id = sessions.speaker_id
        LEFT JOIN session_analytics ON session_analytics.session_id = sessions.id
        ORDER BY sessions.session_date, sessions.start_time
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    for r in rows:
        reg = r["attendees_registered"] or 0
        present = r["attendees_present"] or 0
        r["attendance_rate"] = round((present / reg) * 100, 1) if reg else 0
        r["occupancy_pct"] = round((present / r["venue_capacity"]) * 100, 1) if r["venue_capacity"] else 0
        # Transparent popularity score: 40% attendance rate + 40% avg
        # rating (scaled to 100) + 20% feedback volume (capped at 20 responses).
        rating_component = ((r["avg_rating"] or 0) / 5) * 100
        feedback_component = min((r["feedback_count"] or 0) / 20, 1) * 100
        r["popularity_score"] = round(
            r["attendance_rate"] * 0.4 + rating_component * 0.4 + feedback_component * 0.2, 1
        )
    return rows


def get_session_analytics_summary():
    sessions = get_session_analytics_all()
    total_sessions = len(sessions)

    analyzed = [s for s in sessions if s["attendees_registered"]]
    avg_attendance_rate = round(
        sum(s["attendance_rate"] for s in analyzed) / len(analyzed), 1
    ) if analyzed else 0
    avg_rating = round(
        sum(s["avg_rating"] or 0 for s in analyzed) / len(analyzed), 2
    ) if analyzed else 0
    avg_occupancy = round(
        sum(s["occupancy_pct"] for s in analyzed if s["occupancy_pct"]) /
        max(1, len([s for s in analyzed if s["occupancy_pct"]])), 1
    ) if analyzed else 0

    most_popular = sorted(analyzed, key=lambda s: s["popularity_score"], reverse=True)[:5]

    # Peak attendance time bucket (by start hour).
    hour_totals = {}
    for s in analyzed:
        hour = s["start_time"].split(":")[0] + ":00"
        hour_totals[hour] = hour_totals.get(hour, 0) + (s["attendees_present"] or 0)

    # Venue utilization aggregate across all bookings.
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT venues.name AS venue_name, venues.capacity,
               AVG(CAST(venue_bookings.attendees AS FLOAT) / venues.capacity) * 100 AS avg_utilization,
               COUNT(venue_bookings.id) AS bookings_count
        FROM venue_bookings
        JOIN venues ON venues.id = venue_bookings.venue_id
        WHERE venue_bookings.status = 'Booked'
        GROUP BY venues.id
        ORDER BY avg_utilization DESC
    """)
    venue_utilization = [dict(r) for r in cur.fetchall()]
    for v in venue_utilization:
        v["avg_utilization"] = round(v["avg_utilization"], 1) if v["avg_utilization"] else 0

    # Speaker performance: average rating + number of confirmed sessions.
    cur.execute("""
        SELECT speakers.name AS speaker_name, speakers.rating, speakers.sessions_count,
               COUNT(sessions.id) AS assigned_sessions
        FROM speakers
        LEFT JOIN sessions ON sessions.speaker_id = speakers.id AND sessions.status != 'Cancelled'
        GROUP BY speakers.id
        ORDER BY speakers.rating DESC
    """)
    speaker_performance = [dict(r) for r in cur.fetchall()]
    conn.close()

    return {
        "total_sessions": total_sessions,
        "avg_attendance_rate": avg_attendance_rate,
        "avg_rating": avg_rating,
        "avg_occupancy": avg_occupancy,
        "most_popular": most_popular,
        "peak_hours": hour_totals,
        "venue_utilization": venue_utilization,
        "speaker_performance": speaker_performance,
        "sessions": sessions,
    }


# =======================================================================
# MILESTONE 3 — Sponsorship & Incident Management
# Functional areas: Sponsorship Agent, Incident Agent, Incident Alert
# System, Sponsor Performance Tracking. All functions below operate on
# the same shared SQLite database as Milestone 1 and Milestone 2 --
# nothing above this block was changed.
# =======================================================================

# -----------------------------------------------------------------
# Sponsors
# -----------------------------------------------------------------
def insert_sponsor(record: dict) -> int:
    record.setdefault("added_by", "Prethie K")
    record.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO sponsors
            (name, package, contact_person, contact_email, contract_status,
             payment_status, payment_amount, branding_status, engagement_pct,
             booth_visits, leads_generated, session_participation,
             social_engagement_pct, satisfaction_score, conversion_rate,
             status, added_by, created_at)
        VALUES (:name, :package, :contact_person, :contact_email, :contract_status,
                :payment_status, :payment_amount, :branding_status, :engagement_pct,
                :booth_visits, :leads_generated, :session_participation,
                :social_engagement_pct, :satisfaction_score, :conversion_rate,
                :status, :added_by, :created_at)
    """, record)
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_all_sponsors(search=None, package=None, status=None):
    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT * FROM sponsors WHERE 1=1"
    params = []
    if search:
        query += " AND (name LIKE ? OR contact_person LIKE ? OR contact_email LIKE ?)"
        like = f"%{search}%"
        params += [like, like, like]
    if package and package != "All":
        query += " AND package = ?"
        params.append(package)
    if status and status != "All":
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY engagement_pct DESC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_sponsor(sponsor_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM sponsors WHERE id = ?", (sponsor_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_deliverables_for_sponsor(sponsor_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM sponsor_deliverables WHERE sponsor_id = ? ORDER BY due_date ASC",
        (sponsor_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_all_deliverables(status=None):
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT sponsor_deliverables.*, sponsors.name AS sponsor_name
        FROM sponsor_deliverables
        JOIN sponsors ON sponsors.id = sponsor_deliverables.sponsor_id
        WHERE 1=1
    """
    params = []
    if status and status != "All":
        query += " AND sponsor_deliverables.status = ?"
        params.append(status)
    query += " ORDER BY sponsor_deliverables.due_date ASC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def insert_deliverable(sponsor_id, deliverable, category, due_date, status="Pending"):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO sponsor_deliverables (sponsor_id, deliverable, category, due_date, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (sponsor_id, deliverable, category, due_date, status,
          datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def update_deliverable_status(deliverable_id, status):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE sponsor_deliverables SET status = ? WHERE id = ?", (status, deliverable_id))
    conn.commit()
    conn.close()


def get_sponsor_performance_data():
    """Every sponsor joined with its deliverable-completion percentage --
    the core dataset for the Sponsor Performance dashboard."""
    sponsors = get_all_sponsors()
    conn = get_connection()
    cur = conn.cursor()
    for s in sponsors:
        cur.execute("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) AS completed
            FROM sponsor_deliverables WHERE sponsor_id = ?
        """, (s["id"],))
        row = cur.fetchone()
        total = row["total"] or 0
        completed = row["completed"] or 0
        s["deliverables_total"] = total
        s["deliverables_completed"] = completed
        s["deliverables_pending"] = total - completed
        s["deliverable_completion_pct"] = round((completed / total) * 100, 1) if total else 100.0
    conn.close()
    return sponsors


def get_sponsor_stats():
    sponsors = get_all_sponsors()
    total = len(sponsors)
    active = len([s for s in sponsors if s["status"] == "Active"])
    avg_engagement = round(sum(s["engagement_pct"] for s in sponsors) / total, 1) if total else 0
    total_leads = sum(s["leads_generated"] for s in sponsors)
    avg_conversion = round(sum(s["conversion_rate"] for s in sponsors) / total, 1) if total else 0
    pending_deliverables = len([d for d in get_all_deliverables() if d["status"] != "Completed"])
    return {
        "total_sponsors": total,
        "active_sponsors": active,
        "avg_engagement": avg_engagement,
        "total_leads": total_leads,
        "avg_conversion": avg_conversion,
        "pending_deliverables": pending_deliverables,
    }


# -----------------------------------------------------------------
# Incidents
# -----------------------------------------------------------------
def insert_incident(record: dict) -> int:
    record.setdefault("reported_by", "Prethie K")
    record.setdefault("reported_at", datetime.now().isoformat(timespec="seconds"))
    record.setdefault("status", "Open")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO incidents
            (title, description, category, severity, priority, affected_area,
             responsible_team, recommended_action, alert_type, status,
             reported_by, reported_at, resolved_at)
        VALUES (:title, :description, :category, :severity, :priority, :affected_area,
                :responsible_team, :recommended_action, :alert_type, :status,
                :reported_by, :reported_at, NULL)
    """, record)
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_all_incidents(status=None, priority=None, category=None, search=None):
    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT * FROM incidents WHERE 1=1"
    params = []
    if status and status != "All":
        query += " AND status = ?"
        params.append(status)
    if priority and priority != "All":
        query += " AND priority = ?"
        params.append(priority)
    if category and category != "All":
        query += " AND category = ?"
        params.append(category)
    if search:
        query += " AND (title LIKE ? OR affected_area LIKE ? OR description LIKE ?)"
        like = f"%{search}%"
        params += [like, like, like]
    query += """
        ORDER BY
            CASE priority WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END,
            CASE status WHEN 'Open' THEN 0 WHEN 'In Progress' THEN 1 ELSE 2 END,
            reported_at DESC
    """
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_incident(incident_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def update_incident_status(incident_id, status):
    conn = get_connection()
    cur = conn.cursor()
    resolved_at = datetime.now().isoformat(timespec="seconds") if status == "Resolved" else None
    if resolved_at:
        cur.execute("UPDATE incidents SET status = ?, resolved_at = ? WHERE id = ?",
                     (status, resolved_at, incident_id))
    else:
        cur.execute("UPDATE incidents SET status = ? WHERE id = ?", (status, incident_id))
    conn.commit()
    conn.close()

    # Keep the linked alert's status roughly in sync with the incident.
    conn = get_connection()
    cur = conn.cursor()
    alert_status = "Resolved" if status == "Resolved" else "Active"
    cur.execute(
        "UPDATE alerts SET status = ? WHERE related_incident_id = ?",
        (alert_status, incident_id),
    )
    conn.commit()
    conn.close()


def get_incident_stats():
    incidents = get_all_incidents()
    total = len(incidents)
    open_count = len([i for i in incidents if i["status"] == "Open"])
    in_progress = len([i for i in incidents if i["status"] == "In Progress"])
    resolved = len([i for i in incidents if i["status"] == "Resolved"])
    critical = len([i for i in incidents if i["priority"] == "Critical" and i["status"] != "Resolved"])
    high = len([i for i in incidents if i["priority"] == "High" and i["status"] != "Resolved"])
    by_category = {}
    for i in incidents:
        by_category[i["category"]] = by_category.get(i["category"], 0) + 1
    by_date = {}
    for i in incidents:
        day = i["reported_at"][:10]
        by_date[day] = by_date.get(day, 0) + 1
    return {
        "total": total,
        "open": open_count,
        "in_progress": in_progress,
        "resolved": resolved,
        "critical": critical,
        "high": high,
        "by_category": by_category,
        "by_date": dict(sorted(by_date.items())),
    }


# -----------------------------------------------------------------
# Alerts
# -----------------------------------------------------------------
def insert_alert(record: dict) -> int:
    record.setdefault("status", "Active")
    record.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO alerts
            (alert_type, category, title, description, recommended_action,
             status, related_incident_id, related_sponsor_id, created_at)
        VALUES (:alert_type, :category, :title, :description, :recommended_action,
                :status, :related_incident_id, :related_sponsor_id, :created_at)
    """, record)
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_all_alerts(alert_type=None, status=None):
    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT * FROM alerts WHERE 1=1"
    params = []
    if alert_type and alert_type != "All":
        query += " AND alert_type = ?"
        params.append(alert_type)
    if status and status != "All":
        query += " AND status = ?"
        params.append(status)
    query += """
        ORDER BY
            CASE alert_type WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END,
            created_at DESC
    """
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def update_alert_status(alert_id, status):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE alerts SET status = ? WHERE id = ?", (status, alert_id))
    conn.commit()
    conn.close()


def get_alert_counts():
    alerts = get_all_alerts()
    counts = {"Critical": 0, "High": 0, "Medium": 0, "Informational": 0}
    for a in alerts:
        if a["alert_type"] in counts:
            counts[a["alert_type"]] += 1
    counts["active"] = len([a for a in alerts if a["status"] == "Active"])
    counts["total"] = len(alerts)
    return counts


# -----------------------------------------------------------------
# Milestone 3 combined operational dashboard
# -----------------------------------------------------------------
def get_milestone3_dashboard():
    sponsor_stats = get_sponsor_stats()
    incident_stats = get_incident_stats()
    alert_counts = get_alert_counts()
    sponsor_perf = get_sponsor_performance_data()
    return {
        "sponsor_stats": sponsor_stats,
        "incident_stats": incident_stats,
        "alert_counts": alert_counts,
        "sponsor_performance": sponsor_perf,
    }


# =======================================================================
# MILESTONE 4 -- Event Intelligence & Enterprise Deployment
# Functional areas: Event Intelligence Engine, Agent Orchestration,
# Executive Dashboard. All functions below read the same M1+M2+M3
# tables above (read-only aggregation) plus the two new M4 tables
# (orchestration_log, intelligence_snapshots). Nothing above this
# block was changed.
# =======================================================================

def insert_orchestration_step(run_id, workflow_name, step_number, agent_name,
                               action, input_summary="", output_summary="",
                               status="Success"):
    """Records one step of an orchestrated multi-agent workflow so the
    Agent Orchestration page can show exactly which agent ran, in what
    order, with what input/output -- the orchestration audit trail."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO orchestration_log
            (run_id, workflow_name, step_number, agent_name, action,
             input_summary, output_summary, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (run_id, workflow_name, step_number, agent_name, action,
          input_summary, output_summary, status,
          datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_orchestration_runs(limit=10):
    """Returns the most recent orchestration runs, each as a dict with
    its ordered list of steps -- newest run first."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT run_id, workflow_name, MIN(created_at) AS started_at
        FROM orchestration_log GROUP BY run_id
        ORDER BY started_at DESC LIMIT ?
    """, (limit,))
    runs = [dict(r) for r in cur.fetchall()]
    for run in runs:
        cur.execute("""
            SELECT * FROM orchestration_log WHERE run_id = ?
            ORDER BY step_number ASC
        """, (run["run_id"],))
        run["steps"] = [dict(r) for r in cur.fetchall()]
    conn.close()
    return runs


def get_recent_orchestration_log(limit=50):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orchestration_log ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def insert_intelligence_snapshot(event_health_score, event_health_label,
                                  risks_json, recommendations_json, kpi_json):
    """Persists one Event Intelligence Engine run so the Executive
    Dashboard / Intelligence Engine page can show the health trend over
    time instead of only the latest value."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO intelligence_snapshots
            (event_health_score, event_health_label, risks_json,
             recommendations_json, kpi_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (event_health_score, event_health_label, risks_json,
          recommendations_json, kpi_json,
          datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_intelligence_snapshot_history(limit=20):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, event_health_score, event_health_label, created_at
        FROM intelligence_snapshots ORDER BY id DESC LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return list(reversed(rows))


def get_all_data_for_intelligence_engine():
    """Single aggregation point: pulls the live cross-milestone data the
    Event Intelligence Engine needs (M1 registration/check-in stats, M2
    venue/speaker/session analytics, M3 sponsor/incident/alert data) so
    intelligence_engine.py never talks to the database directly -- it
    stays a pure, testable analysis layer on top of this dict."""
    return {
        "attendee_stats": get_stats(),
        "session_summary": get_session_analytics_summary(),
        "sponsor_stats": get_sponsor_stats(),
        "sponsor_performance": get_sponsor_performance_data(),
        "incident_stats": get_incident_stats(),
        "alert_counts": get_alert_counts(),
        "all_incidents": get_all_incidents(),
        "all_sessions": get_all_sessions(),
        "all_venues": get_all_venues(),
    }


# =======================================================================
# MILESTONE 4 -- Testing Center data access
# =======================================================================

def insert_test_run(total, passed, failed, errors, duration_seconds,
                     category_json, raw_output, triggered_by="Manual"):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO test_runs
            (total, passed, failed, errors, duration_seconds, category_json,
             raw_output, triggered_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (total, passed, failed, errors, duration_seconds, category_json,
          raw_output, triggered_by, datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_latest_test_run():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM test_runs ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_test_run_history(limit=10):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM test_runs ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows
