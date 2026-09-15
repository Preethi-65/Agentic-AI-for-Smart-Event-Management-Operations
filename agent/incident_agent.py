"""
incident_agent.py
------------------
Milestone 3 — Sponsorship & Incident Management.

This is the "Build Incident Agent" sub-module. Like the Registration,
Venue and Speaker agents from Milestones 1 and 2, it uses transparent,
rule-based scoring rather than a black-box model, so the exact reason
behind every classification decision can be shown in the UI.

Given an incident category and free-text description, the agent
identifies, classifies and prioritizes the incident:

  1. Looks up the category's baseline severity and responsible team
     from CATEGORY_CONFIG.
  2. Scans the description for high-risk keywords (fire, evacuation,
     unconscious, etc.) and escalates severity to Critical when found,
     even if the category's default severity is lower.
  3. Boosts priority when the incident is reported close to the start
     of the next session (imminent-impact escalation).
  4. Maps the final severity to one of the four alert types required
     by the Incident Alert System: Critical, High-Priority,
     Medium-Priority, Informational.

`check_escalation()` implements the "escalate a critical issue that
remains unresolved" automation feature: any Critical/High incident
that has stayed Open past its escalation window is flagged so the
Incident Agent / Alerts UI can surface it without manual monitoring.
"""

from datetime import datetime

# Category -> baseline severity, responsible team, and a concrete
# recommended action. This mirrors the example in the Milestone 3 brief
# (microphone failure in Hall A -> Technical / Medium / High priority /
# AV Team / replace or use backup microphone).
CATEGORY_CONFIG = {
    "Speaker Cancellation": {
        "severity": "High", "team": "Program / Speaker Ops Team",
        "action": "Activate the backup speaker list or merge the session with an adjacent slot.",
    },
    "Venue Technical Failure": {
        "severity": "Medium", "team": "Facilities Team",
        "action": "Dispatch a facilities technician and switch to backup venue systems if available.",
    },
    "Registration System Failure": {
        "severity": "High", "team": "IT Team",
        "action": "Switch to offline/manual registration and restart the registration service.",
    },
    "Network Outage": {
        "severity": "High", "team": "IT / Network Team",
        "action": "Fail over to the backup network or mobile hotspot and notify affected sessions.",
    },
    "Power Failure": {
        "severity": "Critical", "team": "Electrical / Facilities Team",
        "action": "Switch to the backup generator/UPS immediately and prepare evacuation if prolonged.",
    },
    "Overcrowding": {
        "severity": "High", "team": "Security / Venue Team",
        "action": "Open the overflow area, restrict further entry, and deploy additional staff.",
    },
    "Medical Emergency": {
        "severity": "Critical", "team": "Medical Team",
        "action": "Alert on-site medical staff immediately and clear the access path for responders.",
    },
    "Security Issue": {
        "severity": "High", "team": "Security Team",
        "action": "Dispatch security personnel to the location and isolate the affected area.",
    },
    "Audio/Video Failure": {
        "severity": "Medium", "team": "AV Team",
        "action": "Replace the microphone/equipment or switch to the backup AV unit.",
    },
    "Session Delay": {
        "severity": "Medium", "team": "Program Team",
        "action": "Notify attendees of the revised timing and adjust the downstream schedule.",
    },
    "Missing Equipment": {
        "severity": "Medium", "team": "Logistics Team",
        "action": "Retrieve a replacement from the equipment store or borrow from a nearby hall.",
    },
    "Fire-Related Issue": {
        "severity": "Critical", "team": "Fire Safety / Facilities Team",
        "action": "Trigger the evacuation protocol and alert the fire safety team immediately.",
    },
    "Other": {
        "severity": "Medium", "team": "Operations Team",
        "action": "Assess the situation on-site and assign it to the relevant operational team.",
    },
}

INCIDENT_CATEGORIES = list(CATEGORY_CONFIG.keys())

SEVERITY_ORDER = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}

# Keywords in the free-text description that force a Critical severity
# regardless of the category's baseline (safety-first escalation).
HIGH_RISK_KEYWORDS = [
    "fire", "evacuat", "explosion", "unconscious", "collapse", "smoke",
    "life-threatening", "cardiac", "stampede", "bomb", "weapon", "electrocut",
]

# Severity -> alert type shown in the Incident Alert System.
SEVERITY_TO_ALERT_TYPE = {
    "Critical": "Critical",
    "High": "High",
    "Medium": "Medium",
    "Low": "Informational",
}

# How long a Critical/High incident can remain Open before the agent
# flags it as needing escalation (used by check_escalation()).
ESCALATION_WINDOW_HOURS = {"Critical": 1, "High": 3}


def classify_incident(category, description="", minutes_to_next_session=None):
    """Core rule-based classification. Returns a dict with severity,
    priority, responsible_team, recommended_action and alert_type --
    everything the UI needs to display, e.g. for a Hall A microphone
    failure 10 minutes before the next session:
        severity=Medium, priority=High, affected team=AV Team,
        recommended_action='Replace the microphone / use a backup mic'.
    """
    cfg = CATEGORY_CONFIG.get(category, CATEGORY_CONFIG["Other"])
    severity = cfg["severity"]

    text = (description or "").lower()
    if any(keyword in text for keyword in HIGH_RISK_KEYWORDS):
        severity = "Critical"

    priority = severity
    # Imminent-impact escalation: a Medium/Low incident close to the next
    # session start is bumped to High priority so it isn't missed.
    if minutes_to_next_session is not None and minutes_to_next_session <= 15:
        if SEVERITY_ORDER[priority] < SEVERITY_ORDER["High"]:
            priority = "High"

    return {
        "category": category,
        "severity": severity,
        "priority": priority,
        "responsible_team": cfg["team"],
        "recommended_action": cfg["action"],
        "alert_type": SEVERITY_TO_ALERT_TYPE[severity],
    }


def check_escalation(incident):
    """Returns True if an Open/In Progress Critical or High incident has
    stayed unresolved past its escalation window -- implements the
    'escalate a critical issue that remains unresolved' automation."""
    if incident["status"] == "Resolved":
        return False
    window = ESCALATION_WINDOW_HOURS.get(incident["priority"])
    if window is None:
        return False
    try:
        reported = datetime.fromisoformat(incident["reported_at"])
    except (ValueError, TypeError):
        return False
    hours_open = (datetime.now() - reported).total_seconds() / 3600
    return hours_open >= window


def build_recommendation_summary(incidents):
    """Simple AI-style operational recommendation panel: surfaces the
    incidents needing the most urgent attention right now."""
    open_incidents = [i for i in incidents if i["status"] != "Resolved"]
    escalations = [i for i in open_incidents if check_escalation(i)]
    critical_open = [i for i in open_incidents if i["priority"] == "Critical"]
    high_open = [i for i in open_incidents if i["priority"] == "High"]

    recommendations = []
    if escalations:
        recommendations.append(
            f"{len(escalations)} incident(s) have stayed unresolved past their escalation "
            f"window and should be escalated to a senior organizer now."
        )
    if critical_open:
        recommendations.append(
            f"{len(critical_open)} Critical incident(s) are currently open — prioritize these "
            f"before anything else."
        )
    if high_open:
        recommendations.append(
            f"{len(high_open)} High-priority incident(s) need attention within the next hour."
        )
    if not recommendations:
        recommendations.append("No urgent incidents right now — all critical and high-priority items are resolved.")
    return recommendations, escalations
