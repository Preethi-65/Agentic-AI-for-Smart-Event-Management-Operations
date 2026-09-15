"""
intelligence_engine.py
-----------------------
Milestone 4 -- Event Intelligence & Enterprise Deployment.

This is the "Build Event Intelligence Engine" sub-module -- the central
intelligence layer described in the Milestone 4 brief. It does NOT talk
to the database directly (that stays in database.py, via
get_all_data_for_intelligence_engine()) and it does NOT introduce any
external/paid AI API. Like every other agent in this project
(Registration, Venue, Speaker, Sponsorship, Incident) it is transparent
and rule-based: every number in the output can be traced back to the
exact metric and weight that produced it.

The engine pulls together data already produced by Milestones 1-3
(registration/check-in, venue/speaker/session analytics, sponsorship
performance, incidents and alerts) and turns it into:

  1. A single overall EVENT HEALTH SCORE (0-100) and label.
  2. A list of concrete, prioritized RISKS.
  3. A list of concrete, actionable RECOMMENDATIONS.
  4. A compact KPI bundle for the Executive Dashboard.

This module is imported by app.py's /intelligence-engine,
/executive-dashboard and /orchestration routes, and is unit-tested in
tests/test_milestone4.py.
"""

import time

from agent import sponsorship_agent

# ---------------------------------------------------------------------
# Event Health Score weights. Each factor below can only ever subtract
# from a starting score of 100 -- there is no hidden bonus scoring, so
# the number shown on the Executive Dashboard is always explainable as
# "100 minus these specific penalties".
# ---------------------------------------------------------------------
PENALTY_PER_CRITICAL_INCIDENT = 15
PENALTY_PER_HIGH_INCIDENT = 7
PENALTY_PER_ESCALATED_INCIDENT = 5
PENALTY_LOW_CHECKIN_RATE = 12      # applied if check-in rate < 50%
PENALTY_AT_RISK_SPONSOR_RATIO = 25  # scaled by fraction of sponsors At Risk
PENALTY_LOW_SESSION_RATING = 8     # applied if avg session rating < 3.5 / 5

HEALTHY_THRESHOLD = 80
NEEDS_ATTENTION_THRESHOLD = 60

# Simple in-process cache so the Executive Dashboard and Intelligence
# Engine pages (which both call compute_event_intelligence()) do not
# recompute every aggregate on every request -- a Milestone 4
# "Performance Optimization" requirement. TTL-based, no external cache
# server needed for a project of this size.
_CACHE = {"result": None, "computed_at": 0}
_CACHE_TTL_SECONDS = 15


def _label_for_score(score):
    if score >= HEALTHY_THRESHOLD:
        return "Healthy"
    if score >= NEEDS_ATTENTION_THRESHOLD:
        return "Needs Attention"
    return "At Risk"


def _compute_health_score(data):
    """Returns (score, label, penalty_breakdown[list of dict])."""
    score = 100.0
    breakdown = []

    incident_stats = data["incident_stats"]
    critical = incident_stats.get("critical", 0)
    high = incident_stats.get("high", 0)
    if critical:
        deduction = critical * PENALTY_PER_CRITICAL_INCIDENT
        score -= deduction
        breakdown.append({"reason": f"{critical} open Critical incident(s)", "points": -deduction})
    if high:
        deduction = high * PENALTY_PER_HIGH_INCIDENT
        score -= deduction
        breakdown.append({"reason": f"{high} open High-priority incident(s)", "points": -deduction})

    escalated = [i for i in data["all_incidents"]
                 if i["status"] != "Resolved" and _needs_escalation(i)]
    if escalated:
        deduction = len(escalated) * PENALTY_PER_ESCALATED_INCIDENT
        score -= deduction
        breakdown.append({"reason": f"{len(escalated)} incident(s) past their escalation window",
                           "points": -deduction})

    checkin_pct = data["attendee_stats"].get("checkin_pct", 0)
    if checkin_pct < 50:
        score -= PENALTY_LOW_CHECKIN_RATE
        breakdown.append({"reason": f"Check-in rate is only {checkin_pct}%",
                           "points": -PENALTY_LOW_CHECKIN_RATE})

    sponsors = data["sponsor_performance"]
    if sponsors:
        at_risk = [s for s in sponsors if s.get("performance_label") == "At Risk"]
        ratio = len(at_risk) / len(sponsors)
        if ratio > 0:
            deduction = round(ratio * PENALTY_AT_RISK_SPONSOR_RATIO, 1)
            score -= deduction
            breakdown.append({"reason": f"{len(at_risk)}/{len(sponsors)} sponsors are At Risk",
                               "points": -deduction})

    avg_rating = data["session_summary"].get("avg_rating", 0)
    if avg_rating and avg_rating < 3.5:
        score -= PENALTY_LOW_SESSION_RATING
        breakdown.append({"reason": f"Average session rating is only {avg_rating}/5",
                           "points": -PENALTY_LOW_SESSION_RATING})

    score = max(0, min(100, round(score, 1)))
    return score, _label_for_score(score), breakdown


def _needs_escalation(incident):
    """Local, dependency-free mirror of incident_agent.check_escalation()
    so the Intelligence Engine can be unit-tested without importing
    Flask/database context. Kept in sync deliberately -- see
    tests/test_milestone4.py::test_escalation_consistency."""
    from datetime import datetime
    if incident["status"] == "Resolved":
        return False
    window = {"Critical": 1, "High": 3}.get(incident["priority"])
    if window is None:
        return False
    try:
        reported = datetime.fromisoformat(incident["reported_at"])
    except (ValueError, TypeError):
        return False
    hours_open = (datetime.now() - reported).total_seconds() / 3600
    return hours_open >= window


def _identify_risks(data, sponsors_at_risk, escalated):
    risks = []
    incident_stats = data["incident_stats"]

    if incident_stats.get("critical", 0) > 0:
        risks.append({
            "level": "Critical",
            "area": "Incidents",
            "description": f"{incident_stats['critical']} Critical incident(s) are currently open and unresolved.",
        })
    if escalated:
        risks.append({
            "level": "High",
            "area": "Incidents",
            "description": f"{len(escalated)} incident(s) have exceeded their escalation window without resolution.",
        })
    if sponsors_at_risk:
        names = ", ".join(s["name"] for s in sponsors_at_risk[:3])
        risks.append({
            "level": "Medium",
            "area": "Sponsorship",
            "description": f"{len(sponsors_at_risk)} sponsor(s) at risk of not receiving promised benefits: {names}.",
        })
    checkin_pct = data["attendee_stats"].get("checkin_pct", 0)
    if checkin_pct < 50 and data["attendee_stats"].get("total", 0) > 0:
        risks.append({
            "level": "Medium",
            "area": "Attendance",
            "description": f"Only {checkin_pct}% of registered attendees have checked in so far.",
        })
    venue_util = data["session_summary"].get("venue_utilization", [])
    underused = [v for v in venue_util if v.get("avg_utilization", 0) < 30]
    if underused:
        risks.append({
            "level": "Low",
            "area": "Venue",
            "description": f"{len(underused)} venue(s) are running below 30% average utilization.",
        })
    if not risks:
        risks.append({"level": "Low", "area": "Overall", "description": "No significant operational risks detected right now."})
    return risks


def _build_recommendations(data, score, risks):
    recs = []
    for risk in risks:
        if risk["area"] == "Incidents" and risk["level"] in ("Critical", "High"):
            recs.append("Assign a senior organizer to personally track open Critical/High incidents until resolved.")
        elif risk["area"] == "Sponsorship":
            recs.append("Reach out to at-risk sponsors today to close pending deliverables and protect renewal likelihood.")
        elif risk["area"] == "Attendance":
            recs.append("Trigger an on-site reminder push (Notifications module) to lift the check-in rate before sessions fill up.")
        elif risk["area"] == "Venue":
            recs.append("Reassign under-utilized venues to overflow sessions or consolidate the schedule for the next event.")

    if score >= HEALTHY_THRESHOLD:
        recs.append("Event is on track -- maintain current staffing and monitoring cadence.")
    elif score >= NEEDS_ATTENTION_THRESHOLD:
        recs.append("Event is stable but trending down -- review the risks above at the next organizer sync.")
    else:
        recs.append("Event health is low -- convene an emergency organizer huddle to address open Critical/High items immediately.")

    # De-duplicate while preserving order.
    seen = set()
    unique = []
    for r in recs:
        if r not in seen:
            unique.append(r)
            seen.add(r)
    return unique


def compute_event_intelligence(database_module, force_refresh=False):
    """Main entry point. `database_module` is the app's database.py
    module (passed in rather than imported, so this stays testable in
    isolation -- see tests/test_milestone4.py).

    Returns a dict with: score, label, breakdown, risks, recommendations,
    kpis. Cached for _CACHE_TTL_SECONDS to keep dashboard loads fast."""
    now = time.time()
    if not force_refresh and _CACHE["result"] and (now - _CACHE["computed_at"] < _CACHE_TTL_SECONDS):
        return _CACHE["result"]

    data = database_module.get_all_data_for_intelligence_engine()
    # Bug fix: get_all_data_for_intelligence_engine() returns raw sponsor
    # rows straight from the database, without performance_label/
    # performance_score annotated on them (that only happens via
    # sponsorship_agent.annotate_sponsors()). Without this line, every
    # sponsor's performance_label was undefined, so the "At Risk sponsor
    # ratio" health-score penalty, the sponsor risk in _identify_risks(),
    # and sponsors_at_risk below were all silently always empty/zero.
    data["sponsor_performance"] = sponsorship_agent.annotate_sponsors(data["sponsor_performance"])

    score, label, breakdown = _compute_health_score(data)
    sponsors_at_risk = [s for s in data["sponsor_performance"] if s.get("performance_label") == "At Risk"]
    escalated = [i for i in data["all_incidents"] if i["status"] != "Resolved" and _needs_escalation(i)]

    risks = _identify_risks(data, sponsors_at_risk, escalated)
    recommendations = _build_recommendations(data, score, risks)

    attendee_stats = data["attendee_stats"]
    session_summary = data["session_summary"]
    sponsor_stats = data["sponsor_stats"]
    incident_stats = data["incident_stats"]
    alert_counts = data["alert_counts"]

    kpis = {
        "total_registrations": attendee_stats.get("total", 0),
        "checked_in": attendee_stats.get("checked_in", 0),
        "checkin_pct": attendee_stats.get("checkin_pct", 0),
        "sessions_conducted": len([s for s in data["all_sessions"] if s.get("status") == "Completed"]),
        "total_sessions": session_summary.get("total_sessions", 0),
        "avg_session_rating": session_summary.get("avg_rating", 0),
        "avg_venue_occupancy": session_summary.get("avg_occupancy", 0),
        "total_sponsors": sponsor_stats.get("total_sponsors", 0),
        "avg_sponsor_engagement": sponsor_stats.get("avg_engagement", 0),
        "pending_deliverables": sponsor_stats.get("pending_deliverables", 0),
        "sponsors_at_risk": len(sponsors_at_risk),
        "open_incidents": incident_stats.get("open", 0) + incident_stats.get("in_progress", 0),
        "critical_incidents": incident_stats.get("critical", 0),
        "high_incidents": incident_stats.get("high", 0),
        "escalated_incidents": len(escalated),
        "active_alerts": alert_counts.get("active", 0),
        "critical_alerts": alert_counts.get("Critical", 0),
    }

    completion_pct = 0
    if kpis["total_sessions"]:
        completion_pct = round((kpis["sessions_conducted"] / kpis["total_sessions"]) * 100, 1)
    kpis["event_completion_pct"] = completion_pct

    result = {
        "event_health_score": score,
        "event_health_label": label,
        "score_breakdown": breakdown,
        "risks": risks,
        "recommendations": recommendations,
        "kpis": kpis,
        "sponsors_at_risk": sponsors_at_risk,
        "escalated_incidents": escalated,
        "generated_at": now,
    }
    _CACHE["result"] = result
    _CACHE["computed_at"] = now
    _maybe_record_snapshot(database_module, result)
    return result


# Minimum time between passively-recorded snapshots, so the Event Health
# Trend chart accumulates real history from normal page visits without
# flooding the intelligence_snapshots table on every request.
SNAPSHOT_MIN_INTERVAL_SECONDS = 300


def _maybe_record_snapshot(database_module, result):
    """Bug fix: previously, a row was only ever written to
    intelligence_snapshots from inside the Agent Orchestration workflow
    (agent/orchestrator.py). That meant the Event Health Trend chart on
    the Executive Dashboard and Intelligence Engine pages almost never
    had the 2+ data points it needs to render, even though the table and
    chart code were both otherwise correct. This passively records a
    snapshot on normal engine computation too (throttled to at most once
    every 5 minutes), so the trend fills in during ordinary use of the
    application, not only when the orchestrator happens to run.
    Best-effort: never lets a snapshot-recording problem break a
    dashboard page load."""
    try:
        import json
        from datetime import datetime

        recent = database_module.get_intelligence_snapshot_history(limit=1)
        should_record = True
        if recent:
            last_time = datetime.fromisoformat(recent[-1]["created_at"])
            if (datetime.now() - last_time).total_seconds() < SNAPSHOT_MIN_INTERVAL_SECONDS:
                should_record = False
        if should_record:
            database_module.insert_intelligence_snapshot(
                result["event_health_score"], result["event_health_label"],
                json.dumps(result["risks"]), json.dumps(result["recommendations"]),
                json.dumps(result["kpis"]),
            )
    except Exception:
        pass
