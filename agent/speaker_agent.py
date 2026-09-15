"""
speaker_agent.py
------------------
This is the "Build Speaker Agent" sub-module of Milestone 2 (Agentic
AI for Smart Event Management Operations). Like venue_agent.py, it uses fully
local, rule-based scoring logic -- no external AI API is required, so
recommendations are transparent, explainable, and work offline.

Given a session topic and a requested date/time, the Speaker Agent:

  1. Matches the topic against every speaker's expertise list, which
     is stored in the `speaker_expertise` table. Crucially, that table
     is NOT limited to a speaker's original profile -- it also grows
     when an organizer records that a speaker mentioned expertise in
     an additional topic while presenting (see
     database.add_speaker_expertise). This is what allows the agent to
     recommend a speaker for Topic C after they mentioned it in
     passing while delivering a session on Topic A, exactly as
     described in the project brief.
  2. Checks the speaker's existing schedule for a conflicting session
     at the requested date/time (database.check_speaker_availability).
  3. Scores experience and average rating.
  4. Combines everything into a transparent 0-100 Match Score with a
     human-readable list of reasons ("Topic expertise match",
     "Available at requested time", ...), so the ranking is never a
     black box.
  5. Returns speakers ranked by Match Score, clearly separating
     available candidates from those with a scheduling conflict (who
     are still shown, but flagged, with the conflict details).
"""

import database

WEIGHT_TOPIC = 0.40
WEIGHT_AVAILABILITY = 0.20
WEIGHT_EXPERIENCE = 0.15
WEIGHT_RATING = 0.15
WEIGHT_SCHEDULE_COMPAT = 0.10

MAX_EXPERIENCE_YEARS_FOR_FULL_SCORE = 12


class SpeakerRecommendation:
    def __init__(self, speaker):
        self.speaker = speaker
        self.topic_match_pct = 0
        self.matched_topics = []
        self.available = True
        self.conflict = None
        self.score = 0.0
        self.reasons = []

    def to_dict(self):
        return {
            "speaker": self.speaker,
            "topic_match_pct": self.topic_match_pct,
            "matched_topics": self.matched_topics,
            "available": self.available,
            "conflict": self.conflict,
            "score": self.score,
            "reasons": self.reasons,
        }


def _topic_relevance(session_topic, expertise_list):
    """Simple, explainable keyword-overlap relevance: how many words of
    the requested topic appear in the speaker's expertise topics (or
    vice-versa). Case-insensitive, substring-tolerant."""
    session_topic_lower = session_topic.lower().strip()
    matched = []
    for entry in expertise_list:
        topic = entry["topic"]
        topic_lower = topic.lower()
        if topic_lower in session_topic_lower or session_topic_lower in topic_lower:
            matched.append(topic)
            continue
        session_words = set(session_topic_lower.split())
        topic_words = set(topic_lower.split())
        if session_words & topic_words:
            matched.append(topic)

    if not expertise_list:
        return 0, []
    pct = round((len(matched) / max(1, len(expertise_list))) * 100, 1)
    pct = max(pct, 80 if matched else 0)
    return (pct if matched else 0), matched


def recommend_speakers(session_topic, session_date, start_time, end_time, top_n=5):
    """
    Core Speaker Agent logic. Returns:
        {
            "ranked": [...],       # best-first, available and unavailable both included
            "available": [...],    # subset with no conflict
            "conflicted": [...],   # subset with a scheduling conflict
        }
    """
    speakers = database.get_all_speakers()
    results = []

    for speaker in speakers:
        rec = SpeakerRecommendation(speaker)

        topic_pct, matched = _topic_relevance(session_topic, speaker["expertise"])
        rec.topic_match_pct = topic_pct
        rec.matched_topics = matched

        available, conflict = database.check_speaker_availability(
            speaker["id"], session_date, start_time, end_time
        )
        rec.available = available
        rec.conflict = conflict

        experience_score = min(100, (speaker["experience_years"] / MAX_EXPERIENCE_YEARS_FOR_FULL_SCORE) * 100)
        rating_score = (speaker["rating"] / 5) * 100 if speaker["rating"] else 0
        availability_score = 100 if available else 0
        schedule_compat_score = 100 if available else 0

        rec.score = round(
            topic_pct * WEIGHT_TOPIC +
            availability_score * WEIGHT_AVAILABILITY +
            experience_score * WEIGHT_EXPERIENCE +
            rating_score * WEIGHT_RATING +
            schedule_compat_score * WEIGHT_SCHEDULE_COMPAT,
            1,
        )

        if matched:
            rec.reasons.append(f"Topic expertise match ({', '.join(matched)}).")
        else:
            rec.reasons.append("No direct topic expertise on file for this session.")

        if available:
            rec.reasons.append("Available at the requested date and time.")
            rec.reasons.append("No scheduling conflict.")
        else:
            rec.reasons.append(
                f"Scheduling conflict — already assigned to '{conflict['title']}' "
                f"{conflict['start_time']}–{conflict['end_time']} on {conflict['session_date']}."
            )

        if speaker["sessions_count"] >= 5:
            rec.reasons.append(f"Experienced presenter ({speaker['sessions_count']} previous sessions).")
        if speaker["rating"] >= 4.5:
            rec.reasons.append(f"Highly rated by past attendees ({speaker['rating']}/5).")

        results.append(rec)

    results.sort(key=lambda r: r.score, reverse=True)

    available_only = [r for r in results if r.available]
    conflicted_only = [r for r in results if not r.available]

    return {
        "ranked": [r.to_dict() for r in results[:top_n]],
        "available": [r.to_dict() for r in available_only[:top_n]],
        "conflicted": [r.to_dict() for r in conflicted_only[:top_n]],
    }
