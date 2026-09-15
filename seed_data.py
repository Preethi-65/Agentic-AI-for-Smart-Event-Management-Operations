"""
seed_data.py
------------
Optional helper script that populates the system with realistic sample
data for BOTH milestones by running each record through the real
application logic (Registration Agent, Venue Agent scoring, Speaker
Agent scoring) exactly like a live user would trigger it. Useful for
demos, screenshots, and testing every module without manually typing
dozens of entries.

Run with:  python seed_data.py
"""

import random
from datetime import datetime, timedelta

import database
import qr_utils
import notifications
from agent import registration_agent

EVENT_NAMES = [ev[0] for ev in database.DEFAULT_EVENTS]
CITIES = ["Coimbatore", "Chennai", "Bengaluru", "Hyderabad", "Madurai",
          "Pune", "Mumbai", "Delhi", "Kochi", "Tiruppur"]
GENDERS = ["Male", "Female", "Other", "Prefer not to say"]

# ---------------------------------------------------------------------
# Milestone 1 demo attendees
# ---------------------------------------------------------------------
SAMPLE_ATTENDEES = [
    # Prethie K is included as the primary demo attendee referenced
    # throughout the project documentation and output screenshots.
    {"full_name": "preethi k", "email": "preethi.k@psgtech.edu", "phone": "9876501234",
     "organization": "PSG College of Technology", "job_title": "Student", "category": "Auto-detect",
     "age": "21", "gender": "Female", "city": "Coimbatore", "event": "AI Workshop"},
    {"full_name": "ananya sharma", "email": "ananya.sharma@psgtech.edu", "phone": "9876543210",
     "organization": "PSG College of Technology", "job_title": "Final Year Student", "category": "Auto-detect", "age": "21"},
    {"full_name": "rahul verma", "email": "rahul.verma@infosys.com", "phone": "9845123456",
     "organization": "Infosys Technologies", "job_title": "Software Engineer", "category": "Auto-detect", "age": "27"},
    {"full_name": "meera nair", "email": "meera.nair@tce.edu", "phone": "9900112233",
     "organization": "Thiagarajar College of Engineering", "job_title": "Student", "category": "Auto-detect", "age": "20"},
    {"full_name": "arjun iyer", "email": "arjun.iyer@zenithsolutions.com", "phone": "9012345678",
     "organization": "Zenith Solutions Pvt Ltd", "job_title": "Chief Executive Officer", "category": "Auto-detect", "age": "41"},
    {"full_name": "divya reddy", "email": "divya.reddy@gmail.com", "phone": "9765432109",
     "organization": "Freelance", "job_title": "UX Speaker", "category": "Auto-detect", "age": "33"},
    {"full_name": "karthik raja", "email": "karthik.raja@anna.university.edu", "phone": "9345678901",
     "organization": "Anna University", "job_title": "Research Scholar", "category": "Auto-detect", "age": "24"},
    {"full_name": "sneha kulkarni", "email": "sneha.k@brightsys.com", "phone": "9823456701",
     "organization": "Bright Systems Inc", "job_title": "Director of Engineering", "category": "Auto-detect", "age": "38"},
    {"full_name": "vivek menon", "email": "vivek.menon@outlook.com", "phone": "9887766554",
     "organization": "Independent", "job_title": "Attendee", "category": "General", "age": "29"},
    {"full_name": "divya prakash", "email": "divya.prakash@kct.ac.in", "phone": "9776655443",
     "organization": "Kumaraguru College of Technology", "job_title": "Student Volunteer", "category": "Auto-detect", "age": "19"},
    {"full_name": "sanjay gupta", "email": "sanjay.gupta@nexcorp.com", "phone": "9765123489",
     "organization": "NexCorp Technologies", "job_title": "VP of Product", "category": "Auto-detect", "age": "45"},
    {"full_name": "lakshmi venkat", "email": "lakshmi.v@gmail.com", "phone": "9090909090",
     "organization": "PSG Institute of Management", "job_title": "MBA Student", "category": "Auto-detect", "age": "23"},
    {"full_name": "farhan ahmed", "email": "farhan.ahmed@cloudpeak.io", "phone": "9012312312",
     "organization": "CloudPeak Solutions", "job_title": "Head of Cloud Platform", "category": "Auto-detect", "age": "36"},
    {"full_name": "ritika bansal", "email": "ritika.bansal@gmail.com", "phone": "9345098765",
     "organization": "General Public", "job_title": "Visitor", "category": "General", "age": "31"},
    {"full_name": "manoj pillai", "email": "manoj.pillai@srmuniv.edu", "phone": "9988776655",
     "organization": "SRM University", "job_title": "Assistant Professor", "category": "Auto-detect", "age": "52"},
    {"full_name": "aditi rao", "email": "aditi.rao@speakerhub.com", "phone": "9911223344",
     "organization": "SpeakerHub Global", "job_title": "Keynote Speaker", "category": "Auto-detect", "age": "34"},
]

# ---------------------------------------------------------------------
# Milestone 2 demo sessions
# (title, topic, event_name, session_date, start_time, end_time,
#  attendees_expected, facilities_required, preferred_location)
# ---------------------------------------------------------------------
SAMPLE_SESSIONS = [
    ("Introduction to Machine Learning", "Machine Learning", "AI Workshop",
     "2026-08-05", "10:00", "11:30", 140, "Projector,Mic,WiFi", "Block B"),
    ("Deep Learning Foundations", "Deep Learning", "AI Workshop",
     "2026-08-05", "12:00", "13:00", 80, "Projector,WiFi", ""),
    ("Advanced Machine Learning Applications", "Machine Learning", "AI Workshop",
     "2026-08-05", "10:30", "11:30", 60, "Projector,WiFi", ""),
    ("Cloud Architecture Patterns", "Cloud Computing", "Cloud Computing Summit",
     "2026-08-10", "09:30", "11:00", 190, "Projector,Mic,AC,WiFi", ""),
    ("DevOps in Practice", "DevOps", "Cloud Computing Summit",
     "2026-08-10", "11:30", "12:30", 95, "Projector,WiFi", ""),
    ("Building Full Stack Apps", "Full Stack Development", "Full Stack Hackathon",
     "2026-08-15", "09:00", "10:30", 235, "Projector,Mic,AC,WiFi,Recording", ""),
    ("Data Storytelling with Visualization", "Data Visualization", "Data Science Meetup",
     "2026-08-20", "14:00", "15:00", 62, "Projector,Whiteboard", ""),
    ("Ethical Hacking Essentials", "Cyber Security", "Cyber Security Bootcamp",
     "2026-08-25", "11:00", "12:30", 118, "Projector,Mic,AC,WiFi", ""),
]

# (session_title, venue_name) -- which sessions get a venue booked at seed time.
# Session 2 (Deep Learning) and Session 3 (Advanced ML Applications) are
# deliberately left unbooked/unassigned so they can be used to demo the
# Venue Agent, Speaker Agent, and scheduling-conflict detection live.
SESSION_VENUE_BOOKINGS = {
    "Introduction to Machine Learning": "Auditorium A",
    "Cloud Architecture Patterns": "Auditorium B",
    "DevOps in Practice": "Conference Hall",
    "Building Full Stack Apps": "Auditorium B",
    "Data Storytelling with Visualization": "Seminar Hall 1",
    "Ethical Hacking Essentials": "Seminar Hall 2",
}

# (session_title, speaker_name) -- which sessions get a speaker assigned
# at seed time. Note Mr. Rohan Mehta is assigned to two non-overlapping
# sessions on the same day to demonstrate a speaker handling multiple
# sessions without conflict.
SESSION_SPEAKER_ASSIGNMENTS = {
    "Introduction to Machine Learning": "Dr. Anitha Raghavan",
    "Cloud Architecture Patterns": "Mr. Rohan Mehta",
    "DevOps in Practice": "Mr. Rohan Mehta",
    "Building Full Stack Apps": "Ms. Kavya Subramaniam",
    "Data Storytelling with Visualization": "Dr. Sanjay Iyer",
    "Ethical Hacking Essentials": "Ms. Fatima Sheikh",
}

# session_title -> (attendees_registered, attendees_present, avg_rating, feedback_count)
SESSION_ANALYTICS_SEED = {
    "Introduction to Machine Learning": (145, 132, 4.6, 58),
    "Cloud Architecture Patterns": (185, 170, 4.4, 64),
    "DevOps in Practice": (95, 88, 4.3, 40),
    "Building Full Stack Apps": (235, 210, 4.7, 90),
    "Data Storytelling with Visualization": (62, 55, 4.8, 35),
    "Ethical Hacking Essentials": (118, 105, 4.2, 48),
}


def seed_attendees():
    base_time = datetime.now() - timedelta(days=5)
    inserted = 0

    for entry in SAMPLE_ATTENDEES:
        if database.get_attendee_by_email(entry["email"].lower()):
            continue

        entry = dict(entry)
        entry.setdefault("gender", random.choice(GENDERS))
        entry.setdefault("city", random.choice(CITIES))
        entry.setdefault("event", random.choice(EVENT_NAMES))

        decision = registration_agent.process_registration(entry)
        if decision.errors or decision.duplicate:
            continue

        reg_time = base_time + timedelta(hours=random.randint(0, 110))
        record = {
            "reg_code": decision.reg_code,
            "full_name": decision.full_name,
            "email": decision.email,
            "phone": decision.phone,
            "organization": decision.organization,
            "category": decision.category,
            "age": decision.age,
            "gender": decision.gender,
            "city": decision.city,
            "event": decision.event,
            "source": random.choice(["Agent", "Website", "Walk-in"]),
            "risk_flag": decision.risk_flag,
            "registered_at": reg_time.isoformat(timespec="seconds"),
        }
        new_id = database.insert_attendee(record)

        qr_path = qr_utils.generate_qr(decision.reg_code, base_url="http://127.0.0.1:5000")
        database.set_qr_path(new_id, qr_path)

        for note in decision.notes:
            registration_agent.record_log(new_id, note)

        attendee = database.get_attendee_by_code(decision.reg_code)
        event = database.get_event_by_name(decision.event)
        notifications.send_confirmation_email(attendee, event)

        if random.random() < 0.6:
            database.mark_checked_in(record["reg_code"])
            registration_agent.record_log(new_id, "Checked in via Check-in Tracker at the venue.")

        inserted += 1

    print(f"Milestone 1: {inserted} sample attendees inserted.")


def seed_sessions_and_operations():
    venues_by_name = {v["name"]: v for v in database.get_all_venues(status=None)}
    speakers_by_name = {s["name"]: s for s in database.get_all_speakers()}

    sessions_by_title = {}
    created = 0
    for (title, topic, event_name, session_date, start_time, end_time,
         attendees_expected, facilities_required, preferred_location) in SAMPLE_SESSIONS:
        existing = [s for s in database.get_all_sessions() if s["title"] == title]
        if existing:
            sessions_by_title[title] = existing[0]
            continue
        new_session = database.create_session(
            title, topic, event_name, session_date, start_time, end_time,
            attendees_expected, facilities_required, preferred_location,
        )
        sessions_by_title[title] = new_session
        created += 1
    print(f"Milestone 2: {created} sample sessions created.")

    booked = 0
    for title, venue_name in SESSION_VENUE_BOOKINGS.items():
        session = sessions_by_title.get(title)
        venue = venues_by_name.get(venue_name)
        if not session or not venue:
            continue
        available, _ = database.check_venue_availability(
            venue["id"], session["session_date"], session["start_time"], session["end_time"]
        )
        if not available:
            continue
        ok, _ = database.create_booking(
            venue["id"], session["session_date"], session["start_time"], session["end_time"],
            session["attendees_expected"], booked_by="Seed Script", label=title, session_id=session["id"],
        )
        if ok:
            booked += 1
    print(f"Milestone 2: {booked} venue bookings created.")

    assigned = 0
    for title, speaker_name in SESSION_SPEAKER_ASSIGNMENTS.items():
        session = sessions_by_title.get(title)
        speaker = speakers_by_name.get(speaker_name)
        if not session or not speaker:
            continue
        # Refresh session (venue booking above may have updated its status).
        session = database.get_session(session["id"])
        if session["speaker_id"]:
            continue
        ok, _ = database.assign_speaker_to_session(
            session["id"], speaker["id"], match_score=None, reasons="Seeded demo assignment"
        )
        if ok:
            assigned += 1
    print(f"Milestone 2: {assigned} speaker assignments created.")

    analytics_count = 0
    for title, (registered, present, avg_rating, feedback_count) in SESSION_ANALYTICS_SEED.items():
        session = sessions_by_title.get(title)
        if not session:
            continue
        database.upsert_session_analytics(session["id"], registered, present, avg_rating, feedback_count)
        analytics_count += 1
    print(f"Milestone 2: {analytics_count} session analytics records created.")


def run():
    database.init_db()
    seed_attendees()
    seed_sessions_and_operations()
    print("Seed complete.")


if __name__ == "__main__":
    run()
