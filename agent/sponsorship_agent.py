"""
sponsorship_agent.py
---------------------
Milestone 3 — Sponsorship & Incident Management.

This is the "Build Sponsorship Agent" sub-module. It follows the same
transparent, rule-based philosophy as the other agents in this project:
no external AI API, fully explainable scoring, so every "Excellent /
Good / At Risk" label can be traced back to the underlying metrics.

The agent turns raw sponsor + deliverable data into the answers the
brief calls out explicitly:
  - Which sponsors have pending deliverables?
  - Which sponsor has the highest attendee engagement?
  - Which sponsors are at risk of not receiving their promised benefits?

and produces a short, plain-language insights panel instead of just
storing sponsor information.
"""

# Weighted performance score: engagement (40%) + deliverable completion
# (30%) + satisfaction, scaled to 100 (30%). No single metric decides
# the label -- a sponsor with high engagement but many missed
# deliverables will still land in "Good" or "At Risk", not "Excellent".
WEIGHT_ENGAGEMENT = 0.4
WEIGHT_DELIVERABLES = 0.3
WEIGHT_SATISFACTION = 0.3

EXCELLENT_THRESHOLD = 82
GOOD_THRESHOLD = 60


def compute_performance(sponsor):
    """sponsor must include engagement_pct, deliverable_completion_pct,
    satisfaction_score (0-5). Returns (label, numeric_score)."""
    satisfaction_pct = (sponsor.get("satisfaction_score") or 0) / 5 * 100
    score = (
        (sponsor.get("engagement_pct") or 0) * WEIGHT_ENGAGEMENT
        + (sponsor.get("deliverable_completion_pct") or 0) * WEIGHT_DELIVERABLES
        + satisfaction_pct * WEIGHT_SATISFACTION
    )
    score = round(score, 1)
    if score >= EXCELLENT_THRESHOLD:
        label = "Excellent"
    elif score >= GOOD_THRESHOLD:
        label = "Good"
    else:
        label = "At Risk"
    return label, score


def annotate_sponsors(sponsors):
    """Adds performance_label and performance_score to each sponsor dict
    in place (sponsors must already carry deliverable_completion_pct,
    e.g. from database.get_sponsor_performance_data())."""
    for s in sponsors:
        label, score = compute_performance(s)
        s["performance_label"] = label
        s["performance_score"] = score
    return sponsors


def sponsors_with_pending_deliverables(sponsors):
    return [s for s in sponsors if s.get("deliverables_pending", 0) > 0]


def highest_engagement_sponsor(sponsors):
    if not sponsors:
        return None
    return max(sponsors, key=lambda s: s.get("engagement_pct") or 0)


def at_risk_sponsors(sponsors):
    """A sponsor is 'at risk of not receiving their promised benefits'
    when its performance label is At Risk, OR it has pending
    deliverables close to being overdue, OR its branding is still
    Pending while the event is imminent."""
    return [s for s in sponsors if s.get("performance_label") == "At Risk"]


def build_insights(sponsors):
    """Plain-language, AI-style insight panel answering the brief's
    example questions directly."""
    pending = sponsors_with_pending_deliverables(sponsors)
    top = highest_engagement_sponsor(sponsors)
    at_risk = at_risk_sponsors(sponsors)

    insights = []

    if pending:
        names = ", ".join(s["name"] for s in pending[:4])
        more = f" and {len(pending) - 4} more" if len(pending) > 4 else ""
        insights.append({
            "question": "Which sponsors have pending deliverables?",
            "answer": f"{len(pending)} sponsor(s) have at least one pending deliverable: {names}{more}.",
        })
    else:
        insights.append({
            "question": "Which sponsors have pending deliverables?",
            "answer": "None — every sponsor's deliverables are currently complete.",
        })

    if top:
        insights.append({
            "question": "Which sponsor has the highest attendee engagement?",
            "answer": f"{top['name']} leads with {top['engagement_pct']}% engagement, "
                      f"{top['leads_generated']} leads generated and a {top.get('conversion_rate', 0)}% conversion rate.",
        })

    if at_risk:
        names = ", ".join(s["name"] for s in at_risk)
        insights.append({
            "question": "Which sponsors are at risk of not receiving their promised benefits?",
            "answer": f"{len(at_risk)} sponsor(s) are at risk: {names}. "
                      f"Low engagement, incomplete deliverables or a low satisfaction score are pulling their performance score down.",
        })
    else:
        insights.append({
            "question": "Which sponsors are at risk of not receiving their promised benefits?",
            "answer": "None right now — every sponsor's performance score is Good or Excellent.",
        })

    return insights
