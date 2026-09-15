"""
registration_agent.py
----------------------
This is the "Build Registration Agent" sub-module.

It behaves like a lightweight intelligent assistant that sits in front
of the raw registration form. Instead of simply saving whatever the
user types, the agent:

  1. Cleans and normalises incoming data (names, emails, phone numbers).
  2. Auto-generates a unique, human-readable registration code.
  3. Suggests / validates the attendee category using simple rule-based
     keyword intelligence (e.g. organisation name containing "college"
     or "university" -> Student, "inc"/"ltd"/"pvt" -> Corporate).
  4. Performs duplicate-registration detection using email matching.
  5. Assigns a basic risk/priority flag (VIP / Low / Review) based on
     simple heuristics, to demonstrate rule-based "intelligence".
  6. Writes a human-readable trace of every decision it makes to the
     agent activity log, so the process is explainable.

This keeps the "intelligence" transparent and dependency-free (no
external ML libraries needed) while still demonstrating an agent that
reasons over the input before handing clean data to the registration
system (database.py).
"""

import re
import random
import string
from datetime import datetime

from database import get_attendee_by_email, log_agent_message

VIP_KEYWORDS = ["ceo", "founder", "director", "president", "chief", "head of", "vp "]
STUDENT_KEYWORDS = ["college", "university", "institute", "school", "academy"]
CORPORATE_KEYWORDS = ["inc", "ltd", "llc", "pvt", "technologies", "solutions", "systems", "corp"]

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_REGEX = re.compile(r"[^0-9+]")


class AgentDecision:
    """Simple container describing what the agent decided and why."""

    def __init__(self):
        self.notes = []
        self.category = None
        self.risk_flag = "Low"
        self.reg_code = None
        self.duplicate = False
        self.errors = []
        self.age = None
        self.gender = None
        self.city = None
        self.event = None

    def add_note(self, text):
        self.notes.append(text)


def _generate_reg_code(category: str) -> str:
    prefix = {"Student": "STU", "Corporate": "CORP", "Speaker": "SPK",
              "VIP": "VIP", "General": "GEN"}.get(category, "GEN")
    suffix = "".join(random.choices(string.digits, k=5))
    return f"{prefix}-{suffix}"


def _clean_name(name: str) -> str:
    name = " ".join(name.strip().split())
    return name.title()


def _clean_phone(phone: str) -> str:
    if not phone:
        return ""
    return PHONE_REGEX.sub("", phone.strip())


def _infer_category(organization: str, job_title: str, requested_category: str) -> str:
    """Rule-based category inference used when the user leaves the
    category as 'Auto-detect' or as a cross-check/suggestion engine."""
    text = f"{organization} {job_title}".lower()

    if requested_category and requested_category != "Auto-detect":
        return requested_category

    for kw in STUDENT_KEYWORDS:
        if kw in text:
            return "Student"
    for kw in CORPORATE_KEYWORDS:
        if kw in text:
            return "Corporate"
    if "speak" in job_title.lower():
        return "Speaker"
    return "General"


def _infer_risk(job_title: str, category: str) -> str:
    text = job_title.lower()
    for kw in VIP_KEYWORDS:
        if kw in text:
            return "VIP"
    if category == "Speaker":
        return "VIP"
    return "Low"


def process_registration(form_data: dict) -> AgentDecision:
    """
    Main entry point for the intelligent agent.
    Takes raw form input (dict) and returns an AgentDecision object
    containing cleaned values, category, risk flag, reg code and any
    validation errors. Does NOT write to the database itself -- the
    Flask route calls database.insert_attendee() with the final data,
    keeping the agent and the storage layer cleanly separated.
    """
    decision = AgentDecision()

    full_name = _clean_name(form_data.get("full_name", ""))
    email = form_data.get("email", "").strip().lower()
    phone = _clean_phone(form_data.get("phone", ""))
    organization = form_data.get("organization", "").strip()
    job_title = form_data.get("job_title", "").strip()
    requested_category = form_data.get("category", "Auto-detect")

    age_raw = form_data.get("age", "").strip()
    gender = form_data.get("gender", "").strip()
    city = " ".join(form_data.get("city", "").strip().split()).title()
    event = form_data.get("event", "").strip()

    if not full_name:
        decision.errors.append("Full name is required.")
    if not email or not EMAIL_REGEX.match(email):
        decision.errors.append("A valid email address is required.")

    age = None
    if not age_raw:
        decision.errors.append("Age is required.")
    else:
        try:
            age = int(age_raw)
            if age < 1 or age > 120:
                decision.errors.append("Please enter a valid age between 1 and 120.")
        except ValueError:
            decision.errors.append("Age must be a whole number.")

    if not event:
        decision.errors.append("Please select an event to register for.")

    if decision.errors:
        return decision

    existing = get_attendee_by_email(email)
    if existing:
        decision.duplicate = True
        decision.add_note(
            f"Duplicate detected: {email} already registered as {existing['reg_code']}."
        )
        return decision

    category = _infer_category(organization, job_title, requested_category)
    decision.add_note(f"Category resolved to '{category}' using rule-based inference.")

    risk_flag = _infer_risk(job_title, category)
    if risk_flag == "VIP":
        decision.add_note("Priority flag set to VIP based on title/category signals.")

    reg_code = _generate_reg_code(category)
    decision.add_note(f"Generated unique registration code {reg_code}.")

    decision.category = category
    decision.risk_flag = risk_flag
    decision.reg_code = reg_code
    decision.full_name = full_name
    decision.email = email
    decision.phone = phone
    decision.organization = organization
    decision.age = age
    decision.gender = gender
    decision.city = city
    decision.event = event
    return decision


def record_log(attendee_id, message):
    log_agent_message(attendee_id, message)
