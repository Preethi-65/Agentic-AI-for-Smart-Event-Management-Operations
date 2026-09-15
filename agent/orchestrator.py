"""
orchestrator.py
----------------
Milestone 4 -- Event Intelligence & Enterprise Deployment.

This is the "Implement Agent Orchestration" sub-module. It coordinates
the agents that already exist in this project (Registration, Venue,
Speaker, Sponsorship, Incident) so they work together on a single
trigger instead of functioning independently, and it writes an audit
trail of every step to the orchestration_log table so the Agent
Orchestration page can show exactly what happened, in what order.

Implemented workflow -- speaker cancellation, exactly as described in
the Milestone 4 brief's example:

    Speaker Agent            -> detects a speaker cancellation
    Event Intelligence Engine -> analyzes the impact on event health
    Venue Agent               -> checks whether the freed-up slot needs
                                  reassignment
    Registration/Attendee sys -> identifies attendees affected (via the
                                  session's event)
    Incident Agent             -> creates/updates a "Speaker
                                  Cancellation" incident
    Operational Alert          -> notifies the event manager
    Executive Dashboard        -> reflects the impact on next load
                                  (event health is recomputed live)

This is a real, runnable workflow (not documentation-only): triggering
it from /orchestration actually updates the sessions, incidents and
alerts tables through the same functions the rest of the app uses.
"""

import uuid
from datetime import datetime

from agent import incident_agent
from agent import intelligence_engine


def _new_run_id():
    return uuid.uuid4().hex[:10]


def run_speaker_cancellation_workflow(database_module, session_id, reason="Speaker unavailable"):
    """Orchestrates a full speaker-cancellation response across five
    agents/modules for the given session. Returns a summary dict the
    /orchestration route uses to render a result banner, and writes
    every step to orchestration_log for the audit trail.

    This function purposefully calls the SAME functions the rest of the
    app already uses (database.update_session_speaker,
    incident_agent.classify_incident, database.insert_incident,
    database.insert_alert) -- orchestration re-uses existing agents
    rather than re-implementing their logic."""
    run_id = _new_run_id()
    step = 0

    def log(agent_name, action, input_summary="", output_summary="", status="Success"):
        nonlocal step
        step += 1
        database_module.insert_orchestration_step(
            run_id, "Speaker Cancellation Response", step, agent_name,
            action, input_summary, output_summary, status,
        )
        return step

    session = database_module.get_session(session_id)
    if not session:
        log("Orchestrator", "Validate trigger", f"session_id={session_id}",
            "Session not found -- workflow aborted.", status="Failed")
        return {"run_id": run_id, "ok": False, "error": "Session not found."}

    # Step 1: Speaker Agent detects the cancellation.
    old_speaker_id = session.get("speaker_id")
    speaker = database_module.get_speaker(old_speaker_id) if old_speaker_id else None
    speaker_name = speaker["name"] if speaker else "Unassigned"
    log(
        "Speaker Agent", "Detect speaker cancellation",
        input_summary=f"Session '{session['title']}' ({session['event_name']}), speaker={speaker_name}",
        output_summary=f"Speaker '{speaker_name}' marked unavailable. Reason: {reason}",
    )
    database_module.update_session_speaker(session_id, None)

    # Step 2: Event Intelligence Engine analyzes the impact before the fix.
    intel_before = intelligence_engine.compute_event_intelligence(database_module, force_refresh=True)
    log(
        "Event Intelligence Engine", "Analyze impact on event health",
        input_summary="Recompute event health score with speaker removed",
        output_summary=f"Event health = {intel_before['event_health_score']} ({intel_before['event_health_label']})",
    )

    # Step 3: Venue Agent checks whether the booked venue/time is still needed.
    venue = database_module.get_venue(session.get("venue_id")) if session.get("venue_id") else None
    venue_note = (
        f"Venue '{venue['name']}' booking for {session['session_date']} "
        f"{session['start_time']}-{session['end_time']} remains reserved pending a replacement speaker."
        if venue else "No venue was booked for this session."
    )
    log("Venue Agent", "Check venue/time impact",
        input_summary=f"venue_id={session.get('venue_id')}", output_summary=venue_note)

    # Step 4: Registration/Attendee system identifies affected attendees.
    affected = database_module.get_all_attendees(event=session.get("event_name"))
    log(
        "Registration Agent", "Identify affected attendees",
        input_summary=f"event={session.get('event_name')}",
        output_summary=f"{len(affected)} registered attendee(s) for this event may be impacted.",
    )

    # Step 5: Incident Agent creates the incident.
    minutes_to_next = None
    classification = incident_agent.classify_incident(
        "Speaker Cancellation",
        description=f"{speaker_name} cancelled session '{session['title']}'. Reason: {reason}.",
        minutes_to_next_session=minutes_to_next,
    )
    incident_id = database_module.insert_incident({
        "title": f"Speaker cancellation: {session['title']}",
        "description": f"{speaker_name} cancelled '{session['title']}' ({session['event_name']}). Reason: {reason}. "
                        f"{len(affected)} registered attendee(s) affected.",
        "category": classification["category"],
        "severity": classification["severity"],
        "priority": classification["priority"],
        "affected_area": session.get("event_name"),
        "responsible_team": classification["responsible_team"],
        "recommended_action": classification["recommended_action"],
        "alert_type": classification["alert_type"],
        "status": "Open",
        "reported_by": "Orchestration Engine (auto)",
        "reported_at": datetime.now().isoformat(timespec="seconds"),
    })
    log(
        "Incident Agent", "Classify and log incident",
        input_summary=f"category=Speaker Cancellation, session={session['title']}",
        output_summary=f"Incident #{incident_id} created -- severity={classification['severity']}, "
                        f"priority={classification['priority']}, team={classification['responsible_team']}.",
    )

    # Step 6: Operational alert raised for the event manager.
    alert_id = database_module.insert_alert({
        "alert_type": classification["alert_type"],
        "category": "Speaker Operations",
        "title": f"Speaker cancelled: {session['title']}",
        "description": f"{speaker_name} cancelled '{session['title']}'. {classification['recommended_action']}",
        "recommended_action": classification["recommended_action"],
        "related_incident_id": incident_id,
        "related_sponsor_id": None,
    })
    log(
        "Alert System", "Notify event manager",
        input_summary=f"incident_id={incident_id}",
        output_summary=f"Alert #{alert_id} raised ({classification['alert_type']}) and routed to the Alert Center.",
    )

    # Step 7: Executive Dashboard reflects the impact (recompute + persist snapshot).
    intel_after = intelligence_engine.compute_event_intelligence(database_module, force_refresh=True)
    import json
    database_module.insert_intelligence_snapshot(
        intel_after["event_health_score"], intel_after["event_health_label"],
        json.dumps(intel_after["risks"]), json.dumps(intel_after["recommendations"]),
        json.dumps(intel_after["kpis"]),
    )
    log(
        "Executive Dashboard", "Refresh event health snapshot",
        input_summary="Recompute after incident + alert creation",
        output_summary=f"Event health now {intel_after['event_health_score']} "
                        f"({intel_after['event_health_label']}). Snapshot saved for trend history.",
    )

    return {
        "run_id": run_id,
        "ok": True,
        "session": session,
        "incident_id": incident_id,
        "alert_id": alert_id,
        "affected_attendees": len(affected),
        "health_before": intel_before["event_health_score"],
        "health_after": intel_after["event_health_score"],
    }


def get_available_agents():
    """Static registry describing the agents orchestration coordinates
    -- used to render the Agent Orchestration page's status panel."""
    return [
        {"name": "Registration Agent", "domain": "Attendee registration & check-in", "milestone": 1},
        {"name": "Venue Agent", "domain": "Venue capacity & booking", "milestone": 2},
        {"name": "Speaker Agent", "domain": "Speaker matching & scheduling", "milestone": 2},
        {"name": "Sponsorship Agent", "domain": "Sponsor tracking & performance", "milestone": 3},
        {"name": "Incident Agent", "domain": "Incident classification & escalation", "milestone": 3},
        {"name": "Event Intelligence Engine", "domain": "Cross-milestone analysis & event health", "milestone": 4},
    ]
