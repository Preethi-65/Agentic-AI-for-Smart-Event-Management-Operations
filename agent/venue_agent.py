"""
venue_agent.py
---------------
This is the "Build Venue Agent" sub-module of Milestone 2 (Agentic AI
for Smart Event Management Operations). It mirrors the design philosophy of
agent/registration_agent.py from Milestone 1: transparent, rule-based
"intelligence" with no external AI API required, so the project works
reliably offline.

The Venue Agent does not just search venues — it evaluates every
venue against the organizer's requirements and produces a ranked,
explainable recommendation:

  1. Filters out venues that are too small for the expected attendees.
  2. Checks real-time availability against `venue_bookings` for the
     requested date/time (via database.check_venue_availability),
     preventing double-booking.
  3. Computes a utilization percentage (attendees / capacity) for
     every candidate, and scores venues so that a well-utilized,
     right-sized venue outranks an oversized one — e.g. a 200-seat
     hall is preferred over a 500-seat hall for 150 attendees, as
     long as the 200-seat hall is available.
  4. Scores facility match and (optional) preferred-location match.
  5. If every well-sized venue is unavailable, the agent still returns
     the best available larger venue as a clearly-labelled alternative
     instead of leaving the organizer with nothing.

The result is a list of ranked VenueRecommendation objects, each with
a numeric score and a human-readable list of reasons, so the decision
logic is visible in the UI rather than being a black box.
"""

import database

# Ideal utilization band: venues whose utilization falls in this range
# score highest on the "right-sizing" component, so we don't
# automatically recommend the biggest available hall.
IDEAL_UTILIZATION_LOW = 55
IDEAL_UTILIZATION_HIGH = 90


class VenueRecommendation:
    def __init__(self, venue):
        self.venue = venue
        self.available = True
        self.conflict = None
        self.utilization = 0.0
        self.facility_match_pct = 0
        self.matched_facilities = []
        self.missing_facilities = []
        self.location_match = None
        self.score = 0.0
        self.reasons = []
        self.oversized_alternative = False

    def to_dict(self):
        return {
            "venue": self.venue,
            "available": self.available,
            "conflict": self.conflict,
            "utilization": self.utilization,
            "facility_match_pct": self.facility_match_pct,
            "matched_facilities": self.matched_facilities,
            "missing_facilities": self.missing_facilities,
            "location_match": self.location_match,
            "score": self.score,
            "reasons": self.reasons,
            "oversized_alternative": self.oversized_alternative,
        }


def _parse_facilities(text):
    if not text:
        return []
    return [f.strip() for f in text.split(",") if f.strip()]


def _score_utilization(utilization):
    """Reward venues whose utilization sits inside the ideal band;
    penalize both under-utilized (oversized) and over-capacity venues."""
    if utilization > 100:
        return 0  # doesn't actually fit
    if IDEAL_UTILIZATION_LOW <= utilization <= IDEAL_UTILIZATION_HIGH:
        return 100
    if utilization > IDEAL_UTILIZATION_HIGH:
        # Slightly tight but still workable (90-100%)
        return 100 - (utilization - IDEAL_UTILIZATION_HIGH) * 2
    # Below the ideal band -- the further below, the more "oversized"
    # (wasteful) the venue is for this event.
    return max(0, 100 - (IDEAL_UTILIZATION_LOW - utilization) * 1.5)


def recommend_venues(attendees, event_date, start_time, end_time,
                      required_facilities=None, preferred_location=None,
                      event_type=None):
    """
    Core Venue Agent logic. Returns a dict:
        {
            "recommended": VenueRecommendation | None,
            "alternatives": [VenueRecommendation, ...],
            "unavailable": [VenueRecommendation, ...],
            "explanation": str,
        }
    """
    required_facilities = required_facilities or []
    all_venues = database.get_all_venues(status="Active")

    candidates = []
    unavailable = []

    for venue in all_venues:
        rec = VenueRecommendation(venue)

        if venue["capacity"] < attendees:
            continue  # too small -- not a candidate at all

        available, conflict = database.check_venue_availability(
            venue["id"], event_date, start_time, end_time
        )
        rec.available = available
        rec.conflict = conflict

        rec.utilization = round((attendees / venue["capacity"]) * 100, 1)

        venue_facilities = _parse_facilities(venue.get("facilities"))
        venue_facilities_lower = [f.lower() for f in venue_facilities]
        matched = [f for f in required_facilities if f.lower() in venue_facilities_lower]
        missing = [f for f in required_facilities if f.lower() not in venue_facilities_lower]
        rec.matched_facilities = matched
        rec.missing_facilities = missing
        rec.facility_match_pct = round((len(matched) / len(required_facilities)) * 100, 1) \
            if required_facilities else 100

        if preferred_location:
            rec.location_match = preferred_location.lower() in (venue.get("location") or "").lower()
        else:
            rec.location_match = None

        # --- Composite score ---
        utilization_score = _score_utilization(rec.utilization)
        facility_score = rec.facility_match_pct
        location_score = 100 if rec.location_match else (60 if rec.location_match is None else 20)
        cost_score = 100  # neutral unless cost data meaningfully differs; see below

        rec.score = round(
            utilization_score * 0.45 +
            facility_score * 0.25 +
            location_score * 0.15 +
            cost_score * 0.15,
            1,
        )

        # --- Explainability ---
        if rec.utilization > 100:
            pass
        elif IDEAL_UTILIZATION_LOW <= rec.utilization <= IDEAL_UTILIZATION_HIGH:
            rec.reasons.append(f"Well-sized venue — {rec.utilization}% utilization for {attendees} attendees.")
        elif rec.utilization < IDEAL_UTILIZATION_LOW:
            rec.reasons.append(f"Larger than necessary — only {rec.utilization}% utilization (some capacity wasted).")
        else:
            rec.reasons.append(f"Nearly full — {rec.utilization}% utilization, tight but workable.")

        if required_facilities:
            if not missing:
                rec.reasons.append(f"Has all {len(required_facilities)} required facilities.")
            else:
                rec.reasons.append(f"Missing facilities: {', '.join(missing)}.")

        if preferred_location:
            rec.reasons.append(
                "Matches preferred location." if rec.location_match else "Does not match preferred location."
            )

        if not available:
            rec.reasons.append(
                f"Not available — already booked {conflict['start_time']}–{conflict['end_time']} "
                f"on {conflict['booking_date']}."
            )
            unavailable.append(rec)
        else:
            rec.reasons.append("Available for the requested date and time.")
            candidates.append(rec)

    # Sort available candidates by score (right-sized + well-equipped first).
    candidates.sort(key=lambda r: r.score, reverse=True)

    recommended = candidates[0] if candidates else None
    alternatives = candidates[1:6] if len(candidates) > 1 else []
    no_capacity_fits = not candidates and not unavailable  # nothing is even big enough

    explanation = ""
    if recommended:
        # Flag as an "oversized alternative" in the UI if a smaller,
        # better-utilized venue exists but is unavailable for this slot.
        smaller_but_booked = [
            u for u in unavailable if u.venue["capacity"] < recommended.venue["capacity"]
        ]
        if smaller_but_booked and recommended.utilization < IDEAL_UTILIZATION_LOW:
            recommended.oversized_alternative = True
            explanation = (
                f"Smaller, better-utilized halls ({', '.join(u.venue['name'] for u in smaller_but_booked)}) "
                f"are already booked for this slot, so {recommended.venue['name']} "
                f"(capacity {recommended.venue['capacity']}, {recommended.utilization}% utilization) "
                f"is recommended as the best available alternative."
            )
        else:
            explanation = (
                f"{recommended.venue['name']} recommended: capacity {recommended.venue['capacity']} "
                f"gives {recommended.utilization}% utilization for {attendees} attendees, "
                f"a better fit than a larger, under-utilized hall."
            )
    elif no_capacity_fits:
        explanation = (
            f"No single venue can seat {attendees} attendees. Consider splitting the event "
            f"across multiple venues or reducing expected attendance."
        )
    else:
        explanation = (
            "Every venue large enough for this event is already booked for the requested "
            "date and time. Try a different time slot, or see the conflicting bookings below."
        )

    return {
        "recommended": recommended.to_dict() if recommended else None,
        "alternatives": [a.to_dict() for a in alternatives],
        "unavailable": [u.to_dict() for u in unavailable],
        "explanation": explanation,
        "no_capacity_fits": no_capacity_fits,
    }
