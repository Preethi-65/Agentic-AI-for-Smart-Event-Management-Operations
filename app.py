"""
app.py
------
Registration Intelligence and Attendee Management
Main Flask application entry point.

This file wires together all sub-modules into one seamless running
project:

  1. Build Registration Agent        -> agent/registration_agent.py
  2. Integrate Registration System   -> database.py (shared SQLite layer)
  3. Develop Attendee Analytics      -> /analytics route + get_stats()
  4. Create Check-in Tracker         -> /checkin routes (manual + QR)
  5. Generate Registration Dashboard -> /dashboard route (home page)
  6. QR Code Generation & Check-in   -> qr_utils.py + /checkin/<code>
  7. Event Notification & Reminders  -> notifications.py + scheduler.py

Run with:  python app.py
Then open: http://127.0.0.1:5000
"""

import csv
import io
import json
import logging
import os

from flask import (
    Flask, render_template, request, redirect, url_for, flash, jsonify,
    Response,
)
from datetime import datetime

import database
import qr_utils
import notifications
import scheduler
import smtp_config
from config import Config
from agent import registration_agent
from agent import venue_agent
from agent import speaker_agent
from agent import sponsorship_agent
from agent import incident_agent
from agent import intelligence_engine
from agent import orchestrator
from agent import test_runner
from agent import deployment_readiness

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY

# --- Milestone 4: application logging (Platform Reliability) ---------
os.makedirs(os.path.dirname(Config.LOG_FILE), exist_ok=True)
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler(Config.LOG_FILE), logging.StreamHandler()],
)

CATEGORIES = ["Auto-detect", "Student", "Corporate", "Speaker", "VIP", "General"]
FILTER_CATEGORIES = ["All", "Student", "Corporate", "Speaker", "VIP", "General"]
GENDER_OPTIONS = ["Male", "Female", "Other", "Prefer not to say"]


@app.before_request
def ensure_db():
    database.init_db()


# ---------------------------------------------------------------------
# 5. Generate Registration Dashboard  (home page)
# ---------------------------------------------------------------------
@app.route("/")
@app.route("/dashboard")
def dashboard():
    stats = database.get_stats()
    recent = database.get_all_attendees(limit=6)
    logs = database.get_recent_agent_logs(6)
    next_event = database.get_next_upcoming_event()
    return render_template(
        "dashboard.html",
        stats=stats,
        recent=recent,
        logs=logs,
        next_event=next_event,
        active_page="dashboard",
    )


# ---------------------------------------------------------------------
# 1. Build Registration Agent  (registration form + intelligent agent)
# ---------------------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    events = database.get_all_events()

    if request.method == "POST":
        decision = registration_agent.process_registration(request.form)

        if decision.errors:
            for err in decision.errors:
                flash(err, "error")
            return render_template(
                "register.html", categories=CATEGORIES, events=events,
                genders=GENDER_OPTIONS, active_page="register",
                form_data=request.form,
            )

        if decision.duplicate:
            flash(decision.notes[-1], "warning")
            return render_template(
                "register.html", categories=CATEGORIES, events=events,
                genders=GENDER_OPTIONS, active_page="register",
                form_data=request.form,
            )

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
            "source": "Agent",
            "risk_flag": decision.risk_flag,
            "registered_at": datetime.now().isoformat(timespec="seconds"),
        }
        new_id = database.insert_attendee(record)

        # --- QR Code Check-in: generate the attendee's unique QR code ---
        qr_rel_path = qr_utils.generate_qr(decision.reg_code, base_url=request.host_url)
        database.set_qr_path(new_id, qr_rel_path)

        for note in decision.notes:
            registration_agent.record_log(new_id, note)
        registration_agent.record_log(
            new_id, f"Attendee '{decision.full_name}' successfully registered."
        )
        registration_agent.record_log(new_id, "QR check-in code generated.")

        attendee = database.get_attendee_by_code(decision.reg_code)
        event = database.get_event_by_name(decision.event)

        # --- Event Notification & Reminder System: confirmation email ---
        ok, note = notifications.send_confirmation_email(attendee, event)
        registration_agent.record_log(new_id, f"Confirmation email — {note}")

        flash(
            f"Registration successful! Code: {decision.reg_code} "
            f"| Category: {decision.category} | Priority: {decision.risk_flag}",
            "success",
        )
        return render_template(
            "registration_success.html",
            attendee=attendee,
            event=event,
            active_page="register",
        )

    return render_template(
        "register.html", categories=CATEGORIES, events=events,
        genders=GENDER_OPTIONS, active_page="register",
    )


# ---------------------------------------------------------------------
# 2. Integrate Registration System  (unified attendee records / search)
# ---------------------------------------------------------------------
@app.route("/attendees")
def attendees():
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "All")
    checked_in = request.args.get("checked_in", "")
    event = request.args.get("event", "All")
    sort_by = request.args.get("sort_by", "registered_at")
    sort_dir = request.args.get("sort_dir", "desc")
    page = max(1, request.args.get("page", 1, type=int))
    per_page = 10

    total = database.count_attendees(
        search=search or None, category=category, checked_in=checked_in, event=event
    )
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)

    records = database.get_all_attendees(
        search=search or None, category=category, checked_in=checked_in, event=event,
        sort_by=sort_by, sort_dir=sort_dir,
        limit=per_page, offset=(page - 1) * per_page,
    )
    events = database.get_all_events()

    return render_template(
        "attendees.html",
        records=records,
        categories=FILTER_CATEGORIES,
        events=events,
        search=search,
        selected_category=category,
        selected_event=event,
        checked_in=checked_in,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        total_pages=total_pages,
        total=total,
        active_page="attendees",
    )


@app.route("/attendees/export.csv")
def export_attendees_csv():
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "All")
    checked_in = request.args.get("checked_in", "")
    event = request.args.get("event", "All")
    sort_by = request.args.get("sort_by", "registered_at")
    sort_dir = request.args.get("sort_dir", "desc")

    records = database.get_all_attendees(
        search=search or None, category=category, checked_in=checked_in, event=event,
        sort_by=sort_by, sort_dir=sort_dir,
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "Registration ID", "Name", "Email", "Phone", "Age", "Gender", "City",
        "Organization", "Category", "Event", "Registration Date", "Check-in Status",
        "Check-in Time",
    ])
    for a in records:
        writer.writerow([
            a["reg_code"], a["full_name"], a["email"], a.get("phone") or "",
            a.get("age") or "", a.get("gender") or "", a.get("city") or "",
            a.get("organization") or "", a["category"], a.get("event") or "",
            a["registered_at"], "Checked In" if a["checked_in"] else "Not Checked In",
            a.get("checked_in_at") or "",
        ])

    output = buffer.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=attendee_records.csv"},
    )


# ---------------------------------------------------------------------
# 3. Develop Attendee Analytics
# ---------------------------------------------------------------------
@app.route("/analytics")
def analytics():
    stats = database.get_stats()
    return render_template("analytics.html", stats=stats, active_page="analytics")


@app.route("/api/stats")
def api_stats():
    return jsonify(database.get_stats())


# ---------------------------------------------------------------------
# 4. Create Check-in Tracker  (manual entry + QR Code Check-in)
# ---------------------------------------------------------------------
def _checkin_attendee(reg_code, via="Check-in Tracker"):
    """Shared check-in logic used by the manual form, the QR link route,
    and the AJAX camera scanner. Prevents duplicate check-ins."""
    attendee = database.get_attendee_by_code(reg_code)
    if not attendee:
        flash(f"No attendee found with code '{reg_code}'.", "error")
        return None
    if attendee["checked_in"]:
        flash(
            f"{attendee['full_name']} was already checked in at {attendee['checked_in_at']}.",
            "warning",
        )
        return attendee
    database.mark_checked_in(reg_code)
    registration_agent.record_log(attendee["id"], f"Checked in via {via} at the venue.")
    flash(f"Checked in: {attendee['full_name']} ({reg_code})", "success")
    return database.get_attendee_by_code(reg_code)


def _render_checkin_page(result):
    recent_checkins = [a for a in database.get_all_attendees() if a["checked_in"]][:8]
    stats = database.get_stats()
    return render_template(
        "checkin.html",
        result=result,
        recent_checkins=recent_checkins,
        stats=stats,
        active_page="checkin",
    )


@app.route("/checkin", methods=["GET", "POST"])
def checkin():
    result = None
    if request.method == "POST":
        reg_code = request.form.get("reg_code", "").strip().upper()
        result = _checkin_attendee(reg_code)
    return _render_checkin_page(result)


@app.route("/checkin/<reg_code>")
def checkin_via_qr(reg_code):
    """This is the URL encoded inside every attendee's QR code. Scanning
    the QR with any phone camera opens this link and checks the
    attendee in automatically."""
    result = _checkin_attendee(reg_code.strip().upper(), via="QR Code scan")
    return _render_checkin_page(result)


@app.route("/api/checkin/<reg_code>", methods=["POST"])
def api_checkin(reg_code):
    """JSON endpoint used by the in-page camera QR scanner so repeated
    scans don't require a full page reload."""
    code = reg_code.strip().upper()
    attendee = database.get_attendee_by_code(code)
    if not attendee:
        return jsonify({"status": "not_found", "message": f"No attendee found with code '{code}'."})
    if attendee["checked_in"]:
        return jsonify({
            "status": "already",
            "message": f"{attendee['full_name']} is already checked in.",
            "attendee": attendee,
        })
    database.mark_checked_in(code)
    registration_agent.record_log(attendee["id"], "Checked in via QR scanner at the venue.")
    updated = database.get_attendee_by_code(code)
    return jsonify({
        "status": "success",
        "message": f"Checked in: {attendee['full_name']} ({code})",
        "attendee": updated,
    })


# ---------------------------------------------------------------------
# 7. Event Notification & Reminder System
# ---------------------------------------------------------------------
@app.route("/notifications")
def notifications_page():
    log = database.get_notification_log(30)
    return render_template(
        "notifications.html",
        log=log,
        smtp_enabled=smtp_config.SMTP_ENABLED,
        active_page="notifications",
    )


@app.route("/notifications/send-reminders", methods=["POST"])
def send_reminders_now():
    count = notifications.run_due_reminders()
    if count:
        flash(f"Processed {count} due reminder email(s).", "success")
    else:
        flash("No reminder emails were due right now.", "warning")
    return redirect(url_for("notifications_page"))


# =======================================================================
# MILESTONE 2 — Agentic AI for Smart Event Management Operations
# =======================================================================
# Functional areas: Venue Agent, Speaker Agent, Venue Optimization
# Workflows, Speaker Scheduling, Session Analytics -- served via
# Sessions (also the Final Integrated Event Schedule), Venues, Venue
# Agent, Speaker Agent, Speaker Schedule, Session Analytics routes.
# All routes share the same Flask app / database / base template as
# Milestone 1 -- this is one continuous application.

FACILITY_OPTIONS = ["Projector", "Mic", "AC", "WiFi", "Whiteboard",
                     "Stage Lighting", "Recording", "Video Conferencing",
                     "Power Outlets", "Catering Area"]


# -----------------------------------------------------------------
# Sessions  (Create Session + Final Integrated Event Schedule)
# -----------------------------------------------------------------
@app.route("/sessions", methods=["GET", "POST"])
def sessions():
    events = database.get_all_events()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        topic = request.form.get("topic", "").strip()
        event_name = request.form.get("event_name", "").strip()
        session_date = request.form.get("session_date", "").strip()
        start_time = request.form.get("start_time", "").strip()
        end_time = request.form.get("end_time", "").strip()
        attendees_expected = request.form.get("attendees_expected", "0").strip()
        facilities_required = request.form.getlist("facilities_required")
        preferred_location = request.form.get("preferred_location", "").strip()

        errors = []
        if not title:
            errors.append("Session title is required.")
        if not topic:
            errors.append("Session topic is required.")
        if not session_date or not start_time or not end_time:
            errors.append("Session date, start time and end time are all required.")
        if start_time and end_time and start_time >= end_time:
            errors.append("End time must be after start time.")
        try:
            attendees_expected = int(attendees_expected)
            if attendees_expected <= 0:
                errors.append("Expected attendees must be a positive number.")
        except ValueError:
            errors.append("Expected attendees must be a whole number.")

        if errors:
            for e in errors:
                flash(e, "error")
        else:
            new_session = database.create_session(
                title, topic, event_name or None, session_date, start_time, end_time,
                attendees_expected, ",".join(facilities_required), preferred_location,
            )
            flash(f"Session '{title}' created. Now find a venue and speaker for it.", "success")
            return redirect(url_for("venue_agent_page", session_id=new_session["id"]))

    all_sessions = database.get_all_sessions()
    return render_template(
        "sessions.html", sessions=all_sessions, events=events,
        facility_options=FACILITY_OPTIONS, active_page="sessions",
    )


# -----------------------------------------------------------------
# Venues  (management + bookings)
# -----------------------------------------------------------------
@app.route("/venues")
def venues():
    all_venues = database.get_all_venues(status=None)
    bookings = database.get_all_bookings_detailed()
    return render_template(
        "venues.html", venues=all_venues, bookings=bookings, active_page="venues",
    )


@app.route("/venues/bookings/<int:booking_id>/cancel", methods=["POST"])
def cancel_venue_booking(booking_id):
    database.cancel_booking(booking_id)
    flash("Booking cancelled.", "warning")
    return redirect(url_for("venues"))


# -----------------------------------------------------------------
# Venue Agent  (recommend + book)
# -----------------------------------------------------------------
@app.route("/venue-agent", methods=["GET", "POST"])
def venue_agent_page():
    session_id = request.args.get("session_id", type=int) or request.form.get("session_id", type=int)
    linked_session = database.get_session(session_id) if session_id else None
    result = None
    form_data = {}

    if linked_session and request.method == "GET":
        form_data = {
            "attendees": linked_session["attendees_expected"],
            "event_date": linked_session["session_date"],
            "start_time": linked_session["start_time"],
            "end_time": linked_session["end_time"],
            "preferred_location": linked_session.get("preferred_location", ""),
            "required_facilities": (linked_session.get("facilities_required") or "").split(","),
        }

    if request.method == "POST":
        attendees = request.form.get("attendees", type=int) or 0
        event_date = request.form.get("event_date", "").strip()
        start_time = request.form.get("start_time", "").strip()
        end_time = request.form.get("end_time", "").strip()
        event_type = request.form.get("event_type", "").strip()
        preferred_location = request.form.get("preferred_location", "").strip()
        required_facilities = request.form.getlist("required_facilities")

        form_data = {
            "attendees": attendees, "event_date": event_date, "start_time": start_time,
            "end_time": end_time, "event_type": event_type,
            "preferred_location": preferred_location, "required_facilities": required_facilities,
        }

        if not attendees or not event_date or not start_time or not end_time:
            flash("Attendees, date, start time and end time are all required.", "error")
        else:
            result = venue_agent.recommend_venues(
                attendees, event_date, start_time, end_time,
                required_facilities=required_facilities,
                preferred_location=preferred_location or None,
                event_type=event_type or None,
            )

    return render_template(
        "venue_agent.html", result=result, form_data=form_data,
        facility_options=FACILITY_OPTIONS, linked_session=linked_session,
        active_page="venue_agent",
    )


@app.route("/venue-agent/book", methods=["POST"])
def book_venue():
    venue_id = request.form.get("venue_id", type=int)
    session_id = request.form.get("session_id", type=int) or None
    event_date = request.form.get("event_date", "").strip()
    start_time = request.form.get("start_time", "").strip()
    end_time = request.form.get("end_time", "").strip()
    attendees = request.form.get("attendees", type=int) or 0
    label = request.form.get("label", "").strip() or None

    ok, result = database.create_booking(
        venue_id, event_date, start_time, end_time, attendees,
        booked_by="Organizer", label=label, session_id=session_id,
    )
    if ok:
        flash(f"Venue booked successfully: {result['booking_date']} {result['start_time']}–{result['end_time']}.", "success")
        if session_id:
            return redirect(url_for("speaker_agent_page", session_id=session_id))
        return redirect(url_for("venues"))
    else:
        flash(
            f"Booking failed — venue already booked {result['start_time']}–{result['end_time']} "
            f"on {result['booking_date']}.",
            "error",
        )
        if session_id:
            return redirect(url_for("venue_agent_page", session_id=session_id))
        return redirect(url_for("venue_agent_page"))


# -----------------------------------------------------------------
# Speaker Agent  (directory + recommend + assign)
# -----------------------------------------------------------------
@app.route("/speaker-agent", methods=["GET", "POST"])
def speaker_agent_page():
    session_id = request.args.get("session_id", type=int) or request.form.get("session_id", type=int)
    linked_session = database.get_session(session_id) if session_id else None
    all_speakers = database.get_all_speakers()
    result = None
    form_data = {}

    if linked_session and request.method == "GET":
        form_data = {
            "topic": linked_session["topic"],
            "session_date": linked_session["session_date"],
            "start_time": linked_session["start_time"],
            "end_time": linked_session["end_time"],
        }
        result = speaker_agent.recommend_speakers(
            linked_session["topic"], linked_session["session_date"],
            linked_session["start_time"], linked_session["end_time"],
        )

    if request.method == "POST" and request.form.get("action") == "recommend":
        topic = request.form.get("topic", "").strip()
        session_date = request.form.get("session_date", "").strip()
        start_time = request.form.get("start_time", "").strip()
        end_time = request.form.get("end_time", "").strip()
        form_data = {"topic": topic, "session_date": session_date, "start_time": start_time, "end_time": end_time}

        if not topic or not session_date or not start_time or not end_time:
            flash("Topic, date, start time and end time are all required.", "error")
        else:
            result = speaker_agent.recommend_speakers(topic, session_date, start_time, end_time)

    return render_template(
        "speaker_agent.html", result=result, form_data=form_data,
        speakers=all_speakers, linked_session=linked_session, active_page="speaker_agent",
    )


@app.route("/speaker-agent/assign", methods=["POST"])
def assign_speaker():
    session_id = request.form.get("session_id", type=int)
    speaker_id = request.form.get("speaker_id", type=int)
    match_score = request.form.get("match_score", type=float)
    reasons = request.form.get("reasons", "")

    ok, result = database.assign_speaker_to_session(session_id, speaker_id, match_score, reasons)
    if ok:
        flash("Speaker assigned successfully.", "success")
        return redirect(url_for("sessions"))
    else:
        flash(
            f"Scheduling Conflict – Speaker is already assigned during this time "
            f"('{result['title']}', {result['start_time']}–{result['end_time']}).",
            "error",
        )
        return redirect(url_for("speaker_agent_page", session_id=session_id))


@app.route("/speaker-agent/add-expertise", methods=["POST"])
def add_speaker_expertise():
    """Implements the 'speaker mentioned an additional topic while
    presenting' scenario -- adds a new expertise entry so future
    Speaker Agent recommendations can surface this speaker for it."""
    speaker_id = request.form.get("speaker_id", type=int)
    topic = request.form.get("topic", "").strip()
    redirect_to = request.form.get("redirect_to") or url_for("speaker_agent_page")

    if topic:
        added = database.add_speaker_expertise(speaker_id, topic, source="Mentioned during session")
        if added:
            flash(f"Recorded new expertise: '{topic}'. This speaker can now be recommended for it.", "success")
        else:
            flash(f"'{topic}' is already on this speaker's expertise list.", "warning")
    return redirect(redirect_to)


# -----------------------------------------------------------------
# Speaker Schedule
# -----------------------------------------------------------------
@app.route("/speaker-schedule")
def speaker_schedule():
    assignments = database.get_all_speaker_assignments()
    all_speakers = database.get_all_speakers()
    return render_template(
        "speaker_schedule.html", assignments=assignments, speakers=all_speakers,
        active_page="speaker_schedule",
    )


# -----------------------------------------------------------------
# Session Analytics
# -----------------------------------------------------------------
@app.route("/session-analytics")
def session_analytics():
    summary = database.get_session_analytics_summary()
    return render_template("session_analytics.html", summary=summary, active_page="session_analytics")


@app.route("/api/session-analytics")
def api_session_analytics():
    return jsonify(database.get_session_analytics_summary())


# =======================================================================
# MILESTONE 3 — Sponsorship & Incident Management
# =======================================================================
# Functional areas: Sponsorship Agent, Sponsor Performance Tracking,
# Incident Agent, Incident Alert System, Milestone 3 Dashboard. All
# routes share the same Flask app / database / base template as
# Milestone 1 and Milestone 2 -- this is one continuous application.

SPONSOR_PACKAGES = ["Platinum", "Gold", "Silver", "Bronze"]
CONTRACT_STATUSES = ["Signed", "Under Negotiation", "Pending"]
PAYMENT_STATUSES = ["Paid", "Partial", "Pending"]
BRANDING_STATUSES = ["Delivered", "In Progress", "Pending"]
DELIVERABLE_CATEGORIES = ["Branding", "Marketing", "Logistics", "Digital", "General"]


# -----------------------------------------------------------------
# Sponsorship Agent  (directory + add sponsor + Q&A insights)
# -----------------------------------------------------------------
@app.route("/sponsorship-agent", methods=["GET", "POST"])
def sponsorship_agent_page():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        package = request.form.get("package", "Bronze")
        contact_person = request.form.get("contact_person", "").strip()
        contact_email = request.form.get("contact_email", "").strip()
        contract_status = request.form.get("contract_status", "Pending")
        payment_status = request.form.get("payment_status", "Pending")
        payment_amount = request.form.get("payment_amount", type=float) or 0
        branding_status = request.form.get("branding_status", "Pending")
        engagement_pct = request.form.get("engagement_pct", type=float) or 0
        booth_visits = request.form.get("booth_visits", type=int) or 0
        leads_generated = request.form.get("leads_generated", type=int) or 0
        session_participation = request.form.get("session_participation", type=int) or 0
        social_engagement_pct = request.form.get("social_engagement_pct", type=float) or 0
        satisfaction_score = request.form.get("satisfaction_score", type=float) or 0
        conversion_rate = request.form.get("conversion_rate", type=float) or 0

        if not name:
            flash("Sponsor name is required.", "error")
        else:
            database.insert_sponsor({
                "name": name, "package": package, "contact_person": contact_person,
                "contact_email": contact_email, "contract_status": contract_status,
                "payment_status": payment_status, "payment_amount": payment_amount,
                "branding_status": branding_status, "engagement_pct": engagement_pct,
                "booth_visits": booth_visits, "leads_generated": leads_generated,
                "session_participation": session_participation,
                "social_engagement_pct": social_engagement_pct,
                "satisfaction_score": satisfaction_score, "conversion_rate": conversion_rate,
                "status": "Active", "added_by": "Prethie K",
            })
            flash(f"Sponsor '{name}' added successfully.", "success")
            return redirect(url_for("sponsorship_agent_page"))

    search = request.args.get("search", "").strip()
    package_filter = request.args.get("package", "All")
    sponsors = sponsorship_agent.annotate_sponsors(database.get_sponsor_performance_data())
    if search:
        s_lower = search.lower()
        sponsors = [s for s in sponsors if s_lower in s["name"].lower()
                    or s_lower in (s.get("contact_person") or "").lower()]
    if package_filter != "All":
        sponsors = [s for s in sponsors if s["package"] == package_filter]

    insights = sponsorship_agent.build_insights(
        sponsorship_agent.annotate_sponsors(database.get_sponsor_performance_data())
    )

    return render_template(
        "sponsorship_agent.html",
        sponsors=sponsors, insights=insights, packages=SPONSOR_PACKAGES,
        contract_statuses=CONTRACT_STATUSES, payment_statuses=PAYMENT_STATUSES,
        branding_statuses=BRANDING_STATUSES, search=search, package_filter=package_filter,
        active_page="sponsorship_agent",
    )


@app.route("/sponsorship-agent/<int:sponsor_id>/add-deliverable", methods=["POST"])
def add_sponsor_deliverable(sponsor_id):
    deliverable = request.form.get("deliverable", "").strip()
    category = request.form.get("category", "General")
    due_date = request.form.get("due_date", "").strip()
    if deliverable:
        database.insert_deliverable(sponsor_id, deliverable, category, due_date or None, "Pending")
        flash(f"Deliverable '{deliverable}' added.", "success")
    return redirect(url_for("sponsorship_agent_page"))


@app.route("/sponsorship-agent/deliverables/<int:deliverable_id>/complete", methods=["POST"])
def complete_sponsor_deliverable(deliverable_id):
    database.update_deliverable_status(deliverable_id, "Completed")
    flash("Deliverable marked as completed.", "success")
    return redirect(request.referrer or url_for("sponsorship_agent_page"))


# -----------------------------------------------------------------
# Sponsor Performance Tracking dashboard
# -----------------------------------------------------------------
@app.route("/sponsor-performance")
def sponsor_performance():
    sponsors = sponsorship_agent.annotate_sponsors(database.get_sponsor_performance_data())
    stats = database.get_sponsor_stats()
    performance_breakdown = {"Excellent": 0, "Good": 0, "At Risk": 0}
    for s in sponsors:
        performance_breakdown[s["performance_label"]] += 1
    return render_template(
        "sponsor_performance.html", sponsors=sponsors, stats=stats,
        performance_breakdown=performance_breakdown, active_page="sponsor_performance",
    )


# -----------------------------------------------------------------
# Incident Agent  (report + classify + directory)
# -----------------------------------------------------------------
@app.route("/incident-agent", methods=["GET", "POST"])
def incident_agent_page():
    classification_result = None

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "Other")
        description = request.form.get("description", "").strip()
        affected_area = request.form.get("affected_area", "").strip()
        minutes_to_next = request.form.get("minutes_to_next_session", type=int)

        if not title or not affected_area:
            flash("Incident title and affected area are required.", "error")
        else:
            classification = incident_agent.classify_incident(category, description, minutes_to_next)
            new_id = database.insert_incident({
                "title": title, "description": description, "category": category,
                "severity": classification["severity"], "priority": classification["priority"],
                "affected_area": affected_area, "responsible_team": classification["responsible_team"],
                "recommended_action": classification["recommended_action"],
                "alert_type": classification["alert_type"], "status": "Open",
                "reported_by": "Prethie K",
            })
            database.insert_alert({
                "alert_type": classification["alert_type"], "category": "Incident",
                "title": f"{category}: {title}", "description": description,
                "recommended_action": classification["recommended_action"],
                "status": "Active", "related_incident_id": new_id, "related_sponsor_id": None,
            })
            classification_result = classification
            classification_result["title"] = title
            classification_result["affected_area"] = affected_area
            flash(
                f"Incident logged and classified — Severity: {classification['severity']} | "
                f"Priority: {classification['priority']} | Team: {classification['responsible_team']}",
                "success",
            )

    status_filter = request.args.get("status", "All")
    priority_filter = request.args.get("priority", "All")
    category_filter = request.args.get("category", "All")
    search = request.args.get("search", "").strip()

    incidents = database.get_all_incidents(
        status=status_filter, priority=priority_filter, category=category_filter, search=search or None,
    )
    for i in incidents:
        i["needs_escalation"] = incident_agent.check_escalation(i)

    recommendations, escalations = incident_agent.build_recommendation_summary(database.get_all_incidents())

    return render_template(
        "incident_agent.html",
        incidents=incidents, categories=incident_agent.INCIDENT_CATEGORIES,
        classification_result=classification_result, status_filter=status_filter,
        priority_filter=priority_filter, category_filter=category_filter, search=search,
        recommendations=recommendations, escalations=escalations,
        active_page="incident_agent",
    )


@app.route("/incident-agent/<int:incident_id>/status", methods=["POST"])
def update_incident_status(incident_id):
    status = request.form.get("status", "Open")
    database.update_incident_status(incident_id, status)
    flash(f"Incident status updated to '{status}'.", "success")
    return redirect(request.referrer or url_for("incident_agent_page"))


# -----------------------------------------------------------------
# Incident Alert System — Alert Center
# -----------------------------------------------------------------
@app.route("/alerts")
def alerts_center():
    alert_type_filter = request.args.get("alert_type", "All")
    status_filter = request.args.get("status", "All")
    alerts = database.get_all_alerts(alert_type=alert_type_filter, status=status_filter)
    counts = database.get_alert_counts()
    return render_template(
        "alerts.html", alerts=alerts, counts=counts,
        alert_type_filter=alert_type_filter, status_filter=status_filter,
        active_page="alerts",
    )


@app.route("/alerts/<int:alert_id>/status", methods=["POST"])
def update_alert_status(alert_id):
    status = request.form.get("status", "Active")
    database.update_alert_status(alert_id, status)
    flash(f"Alert status updated to '{status}'.", "success")
    return redirect(request.referrer or url_for("alerts_center"))


# -----------------------------------------------------------------
# Milestone 3 Operational Dashboard
# -----------------------------------------------------------------
@app.route("/milestone3-dashboard")
def milestone3_dashboard():
    data = database.get_milestone3_dashboard()
    sponsors = sponsorship_agent.annotate_sponsors(data["sponsor_performance"])
    performance_breakdown = {"Excellent": 0, "Good": 0, "At Risk": 0}
    for s in sponsors:
        performance_breakdown[s["performance_label"]] += 1
    incident_stats = data["incident_stats"]
    alert_counts = data["alert_counts"]
    return render_template(
        "milestone3_dashboard.html",
        sponsor_stats=data["sponsor_stats"], incident_stats=incident_stats,
        alert_counts=alert_counts, sponsors=sponsors,
        performance_breakdown=performance_breakdown,
        active_page="milestone3_dashboard",
    )


@app.route("/api/milestone3-dashboard")
def api_milestone3_dashboard():
    return jsonify(database.get_milestone3_dashboard())


# =======================================================================
# MILESTONE 4 -- Event Intelligence & Enterprise Deployment
# Routes only: all logic lives in agent/intelligence_engine.py and
# agent/orchestrator.py, and all data access lives in database.py --
# app.py stays a thin routing layer, consistent with M1/M2/M3.
# =======================================================================

@app.route("/intelligence-engine")
def intelligence_engine_page():
    intel = intelligence_engine.compute_event_intelligence(database)
    history = database.get_intelligence_snapshot_history(limit=15)
    return render_template(
        "intelligence_engine.html", intel=intel, history=history,
        active_page="intelligence_engine",
    )


@app.route("/api/intelligence-engine")
def api_intelligence_engine():
    intel = intelligence_engine.compute_event_intelligence(database, force_refresh=True)
    return jsonify(intel)


@app.route("/orchestration", methods=["GET", "POST"])
def orchestration_page():
    result = None
    if request.method == "POST":
        session_id = request.form.get("session_id", type=int)
        reason = request.form.get("reason", "").strip() or "Speaker unavailable"
        if not session_id:
            flash("Please choose a session to simulate a cancellation for.", "error")
        else:
            result = orchestrator.run_speaker_cancellation_workflow(database, session_id, reason)
            if result.get("ok"):
                flash(
                    f"Workflow complete: Incident #{result['incident_id']} and Alert #{result['alert_id']} "
                    f"created. Event health {result['health_before']} -> {result['health_after']}.",
                    "success",
                )
            else:
                flash(f"Workflow could not run: {result.get('error')}", "error")

    sessions = [s for s in database.get_all_sessions() if s["status"] != "Cancelled"]
    runs = database.get_orchestration_runs(limit=8)
    agents = orchestrator.get_available_agents()
    return render_template(
        "orchestration.html", sessions=sessions, runs=runs, agents=agents,
        result=result, active_page="orchestration",
    )


@app.route("/api/orchestration/runs")
def api_orchestration_runs():
    return jsonify(database.get_orchestration_runs(limit=20))


@app.route("/executive-dashboard")
def executive_dashboard():
    intel = intelligence_engine.compute_event_intelligence(database)
    m3 = database.get_milestone3_dashboard()
    # Bug fix: get_milestone3_dashboard() returns raw sponsor rows without
    # performance_label/performance_score -- those are only added by
    # sponsorship_agent.annotate_sponsors(), exactly as the working
    # /milestone3-dashboard route already does below. Without this, every
    # sponsor's performance_label is undefined, which broke the Sponsor
    # Performance Distribution chart on this page.
    m3["sponsor_performance"] = sponsorship_agent.annotate_sponsors(m3["sponsor_performance"])
    session_summary = database.get_session_analytics_summary()
    attendee_stats = database.get_stats()
    history = database.get_intelligence_snapshot_history(limit=15)
    return render_template(
        "executive_dashboard.html",
        intel=intel, m3=m3, session_summary=session_summary,
        attendee_stats=attendee_stats, history=history,
        active_page="executive_dashboard",
    )


@app.route("/api/executive-dashboard")
def api_executive_dashboard():
    intel = intelligence_engine.compute_event_intelligence(database, force_refresh=True)
    return jsonify({
        "event_health_score": intel["event_health_score"],
        "event_health_label": intel["event_health_label"],
        "kpis": intel["kpis"],
        "risks": intel["risks"],
        "recommendations": intel["recommendations"],
    })


# -----------------------------------------------------------------
# Milestone 4 -- basic error handlers (Platform Reliability)
# -----------------------------------------------------------------
@app.route("/testing-center", methods=["GET", "POST"])
def testing_center():
    result = None
    if request.method == "POST":
        result = test_runner.run_test_suite(triggered_by="Testing Center (manual)")
        if result["failed"] == 0 and result["errors"] == 0:
            flash(f"Test run complete: {result['passed']}/{result['total']} passed in {result['duration_seconds']}s.", "success")
        else:
            flash(f"Test run complete with issues: {result['passed']} passed, {result['failed']} failed, {result['errors']} errors.", "error")

    latest = database.get_latest_test_run()
    history = database.get_test_run_history(limit=10)
    category_results = json.loads(latest["category_json"]) if latest and latest.get("category_json") else {}
    return render_template(
        "testing_center.html", latest=latest, history=history,
        category_results=category_results, result=result,
        active_page="testing_center",
    )


@app.route("/api/testing-center/latest")
def api_testing_center_latest():
    latest = database.get_latest_test_run()
    return jsonify(latest or {})


@app.route("/production-readiness")
def production_readiness_page():
    report = deployment_readiness.get_readiness_report()
    return render_template(
        "production_readiness.html", report=report,
        active_page="production_readiness",
    )


@app.route("/api/production-readiness")
def api_production_readiness():
    return jsonify(deployment_readiness.get_readiness_report())


@app.errorhandler(404)
def handle_404(e):
    return render_template("error.html", code=404,
                            message="Page not found."), 404


@app.errorhandler(500)
def handle_500(e):
    app.logger.exception("Unhandled server error")
    return render_template("error.html", code=500,
                            message="Something went wrong on our end."), 500


if __name__ == "__main__":
    database.init_db()
    scheduler.start()
    app.run(debug=Config.DEBUG, host=Config.HOST, port=Config.PORT)
