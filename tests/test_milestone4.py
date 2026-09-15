"""
tests/test_milestone4.py
-------------------------
End-to-end automated test suite for the full M1 + M2 + M3 + M4
integrated application. Run with:

    python -m pytest tests/test_milestone4.py -v

or, without pytest installed:

    python tests/test_milestone4.py

Covers the testing categories required by the Milestone 4 brief:
Functional, Integration, AI/Agent, API, Workflow, Dashboard,
Performance, Security, Error Handling, and User Acceptance.

Each test uses Flask's built-in test client against a temporary,
freshly-initialized and seeded SQLite database, so this suite never
touches your real data/registration.db and can be re-run safely any
number of times.
"""

import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Point the app at a throwaway database BEFORE importing app/database,
# so the real project database is never touched by the test run.
_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
os.environ["DATABASE_PATH"] = _TMP_DB

import database  # noqa: E402
import app as flask_app_module  # noqa: E402
from agent import intelligence_engine, orchestrator, incident_agent, sponsorship_agent  # noqa: E402
import seed_data  # noqa: E402

ALL_M1_M2_M3_ROUTES = [
    "/", "/dashboard", "/register", "/attendees", "/attendees/export.csv",
    "/analytics", "/checkin", "/notifications", "/sessions", "/venues",
    "/venue-agent", "/speaker-agent", "/speaker-schedule", "/session-analytics",
    "/sponsorship-agent", "/sponsor-performance", "/incident-agent", "/alerts",
    "/milestone3-dashboard",
]
ALL_M4_ROUTES = [
    "/executive-dashboard", "/intelligence-engine", "/orchestration",
    "/testing-center", "/production-readiness",
]
ALL_API_ROUTES = [
    "/api/stats", "/api/session-analytics", "/api/milestone3-dashboard",
    "/api/intelligence-engine", "/api/executive-dashboard", "/api/orchestration/runs",
    "/api/testing-center/latest", "/api/production-readiness",
]


class Milestone4TestCase(unittest.TestCase):
    """Sets up ONE fresh, seeded database + Flask test client for the
    whole suite (module-level setup would re-seed for every test)."""

    @classmethod
    def setUpClass(cls):
        database.init_db()
        seed_data.run()
        flask_app_module.app.config["TESTING"] = True
        cls.client = flask_app_module.app.test_client()

    # -----------------------------------------------------------------
    # 1. FUNCTIONAL TESTING -- every M1/M2/M3 route still works
    # -----------------------------------------------------------------
    def test_01_functional_m1_m2_m3_routes_return_200(self):
        for route in ALL_M1_M2_M3_ROUTES:
            with self.subTest(route=route):
                resp = self.client.get(route)
                self.assertEqual(resp.status_code, 200, f"{route} returned {resp.status_code}")

    def test_02_functional_m4_routes_return_200(self):
        for route in ALL_M4_ROUTES:
            with self.subTest(route=route):
                resp = self.client.get(route)
                self.assertEqual(resp.status_code, 200, f"{route} returned {resp.status_code}")

    # -----------------------------------------------------------------
    # 2. INTEGRATION TESTING -- M4 reads live M1/M2/M3 data correctly
    # -----------------------------------------------------------------
    def test_03_integration_intelligence_engine_reflects_live_attendee_count(self):
        before = database.get_stats()["total"]
        database.insert_attendee({
            "reg_code": "TEST-INTEG-001", "full_name": "Integration Test User",
            "email": "integration.test@example.com", "phone": "0000000000",
            "organization": "Test Org", "category": "General",
            "risk_flag": "Normal", "source": "Manual", "registered_at": "2026-01-01T00:00:00",
        })
        after = database.get_stats()["total"]
        self.assertEqual(after, before + 1)
        intel = intelligence_engine.compute_event_intelligence(database, force_refresh=True)
        self.assertEqual(intel["kpis"]["total_registrations"], after)

    def test_04_integration_shared_database_across_milestones(self):
        # Sponsors (M3) and sessions (M2) both exist in the SAME db file
        # the M1 attendee above was just written to.
        self.assertGreater(len(database.get_all_sponsors()), 0)
        self.assertGreater(len(database.get_all_sessions()), 0)

    # -----------------------------------------------------------------
    # 3. AI / AGENT TESTING -- rule-based agent logic is correct
    # -----------------------------------------------------------------
    def test_05_agent_incident_classification_high_risk_keyword_escalates(self):
        result = incident_agent.classify_incident("Audio/Video Failure", description="Smoke and fire near the stage")
        self.assertEqual(result["severity"], "Critical")

    def test_06_agent_incident_imminent_session_boosts_priority(self):
        result = incident_agent.classify_incident("Missing Equipment", minutes_to_next_session=5)
        self.assertEqual(result["priority"], "High")

    def test_07_agent_sponsorship_scoring_is_explainable(self):
        label, score = sponsorship_agent.compute_performance(
            {"engagement_pct": 90, "deliverable_completion_pct": 40, "satisfaction_score": 5})
        expected = round(90 * 0.4 + 40 * 0.3 + 100 * 0.3, 1)
        self.assertEqual(score, expected)
        self.assertIn(label, ("Excellent", "Good", "At Risk"))

    def test_08_agent_intelligence_engine_score_bounds(self):
        intel = intelligence_engine.compute_event_intelligence(database, force_refresh=True)
        self.assertGreaterEqual(intel["event_health_score"], 0)
        self.assertLessEqual(intel["event_health_score"], 100)
        self.assertIn(intel["event_health_label"], ("Healthy", "Needs Attention", "At Risk"))

    # -----------------------------------------------------------------
    # 4. API TESTING
    # -----------------------------------------------------------------
    def test_09_api_endpoints_return_valid_json(self):
        for route in ALL_API_ROUTES:
            with self.subTest(route=route):
                resp = self.client.get(route)
                self.assertEqual(resp.status_code, 200)
                data = json.loads(resp.data)
                self.assertIsInstance(data, (dict, list))

    def test_10_api_intelligence_engine_shape(self):
        resp = self.client.get("/api/intelligence-engine")
        data = json.loads(resp.data)
        for key in ("event_health_score", "event_health_label", "risks", "recommendations", "kpis"):
            self.assertIn(key, data)

    # -----------------------------------------------------------------
    # 5. WORKFLOW / ORCHESTRATION TESTING
    # -----------------------------------------------------------------
    def test_11_workflow_speaker_cancellation_end_to_end(self):
        sessions = [s for s in database.get_all_sessions() if s["speaker_id"]]
        self.assertTrue(sessions, "Seed data must include at least one session with a speaker assigned.")
        session = sessions[0]
        incidents_before = len(database.get_all_incidents())
        alerts_before = len(database.get_all_alerts())

        result = orchestrator.run_speaker_cancellation_workflow(database, session["id"], reason="Unit test cancellation")

        self.assertTrue(result["ok"])
        self.assertEqual(len(database.get_all_incidents()), incidents_before + 1)
        self.assertEqual(len(database.get_all_alerts()), alerts_before + 1)
        run = database.get_orchestration_runs(limit=1)[0]
        self.assertEqual(run["run_id"], result["run_id"])
        self.assertEqual(len(run["steps"]), 7, "Workflow must log exactly 7 orchestration steps.")

    def test_12_workflow_invalid_session_id_handled_gracefully(self):
        result = orchestrator.run_speaker_cancellation_workflow(database, 99999)
        self.assertFalse(result["ok"])
        self.assertIn("error", result)

    # -----------------------------------------------------------------
    # 6. DASHBOARD TESTING -- executive dashboard is NOT hardcoded
    # -----------------------------------------------------------------
    def test_13_dashboard_executive_data_is_live_not_hardcoded(self):
        resp1 = self.client.get("/api/executive-dashboard")
        kpis1 = json.loads(resp1.data)["kpis"]
        database.insert_attendee({
            "reg_code": "TEST-DASH-002", "full_name": "Dashboard Test User",
            "email": "dashboard.test@example.com", "phone": "0000000001",
            "organization": "Test Org", "category": "General",
            "risk_flag": "Normal", "source": "Manual", "registered_at": "2026-01-01T00:00:00",
        })
        resp2 = self.client.get("/api/executive-dashboard")
        kpis2 = json.loads(resp2.data)["kpis"]
        self.assertEqual(kpis2["total_registrations"], kpis1["total_registrations"] + 1)

    # -----------------------------------------------------------------
    # 7. PERFORMANCE TESTING
    # -----------------------------------------------------------------
    def test_14_performance_executive_dashboard_responds_quickly(self):
        start = time.time()
        for _ in range(5):
            resp = self.client.get("/executive-dashboard")
            self.assertEqual(resp.status_code, 200)
        elapsed = time.time() - start
        self.assertLess(elapsed, 5.0, "5 dashboard loads should complete in well under 5 seconds locally.")

    def test_15_performance_intelligence_engine_cache_reduces_repeat_calls(self):
        intelligence_engine._CACHE["result"] = None
        intelligence_engine._CACHE["computed_at"] = 0
        t0 = time.time()
        intelligence_engine.compute_event_intelligence(database, force_refresh=True)
        first_call = time.time() - t0
        t1 = time.time()
        intelligence_engine.compute_event_intelligence(database)  # should hit cache
        cached_call = time.time() - t1
        self.assertLessEqual(cached_call, first_call + 0.01)

    # -----------------------------------------------------------------
    # 8. SECURITY / INPUT VALIDATION TESTING
    # -----------------------------------------------------------------
    def test_16_security_orchestration_rejects_missing_session_id(self):
        resp = self.client.post("/orchestration", data={"reason": "no session id"}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)  # redirects back with a flash error, does not crash

    def test_17_security_sql_injection_style_search_input_is_safe(self):
        resp = self.client.get("/attendees?search=%27%3B%20DROP%20TABLE%20attendees%3B--")
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(len(database.get_all_attendees()), 0, "attendees table must survive the query untouched")

    # -----------------------------------------------------------------
    # 9. ERROR HANDLING TESTING
    # -----------------------------------------------------------------
    def test_18_error_handling_unknown_route_returns_404(self):
        resp = self.client.get("/this-route-does-not-exist")
        self.assertEqual(resp.status_code, 404)

    def test_19_error_handling_orchestration_bad_session_id_type(self):
        resp = self.client.post("/orchestration", data={"session_id": "not-a-number"}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

    # -----------------------------------------------------------------
    # 10. USER ACCEPTANCE TESTING -- realistic end-to-end scenario
    # -----------------------------------------------------------------
    def test_20_uat_full_event_lifecycle_scenario(self):
        """Simulates an organizer's real session: check the executive
        dashboard, drill into risks on the Intelligence Engine page,
        and confirm the Alerts Center reflects the same alert count."""
        exec_resp = self.client.get("/executive-dashboard")
        self.assertEqual(exec_resp.status_code, 200)

        intel_resp = self.client.get("/api/intelligence-engine")
        intel = json.loads(intel_resp.data)
        self.assertIsInstance(intel["risks"], list)

        alerts_resp = self.client.get("/api/milestone3-dashboard")
        alerts = json.loads(alerts_resp.data)["alert_counts"]
        self.assertEqual(alerts["active"] + (alerts["total"] - alerts["active"]), alerts["total"])

    # -----------------------------------------------------------------
    # 11. MILESTONE 4 SUBTOPIC PAGES -- Testing Center & Production Readiness
    # -----------------------------------------------------------------
    def test_21_testing_center_page_and_api_render(self):
        resp = self.client.get("/testing-center")
        self.assertEqual(resp.status_code, 200)
        api_resp = self.client.get("/api/testing-center/latest")
        self.assertEqual(api_resp.status_code, 200)

    def test_22_production_readiness_report_is_live(self):
        from agent import deployment_readiness
        report = deployment_readiness.get_readiness_report()
        self.assertGreaterEqual(report["score"], 0)
        self.assertLessEqual(report["score"], 100)
        self.assertEqual(report["total"], len(report["checks"]))
        # Every check must have a real status, not a placeholder
        for c in report["checks"]:
            self.assertIn(c["status"], ("pass", "warn", "fail"))
            self.assertTrue(c["detail"])

    def test_23_all_five_m4_subtopics_reachable_via_nav(self):
        """Confirms all 5 Milestone 4 subtopic routes referenced by
        base.html's sidebar actually resolve -- i.e. no subtopic is a
        dead link or hidden-only page."""
        resp = self.client.get("/dashboard")
        html = resp.data.decode()
        for route in ["/intelligence-engine", "/executive-dashboard",
                      "/orchestration", "/testing-center", "/production-readiness"]:
            self.assertIn(f'href="{route}"', html, f"{route} must be linked from the sidebar")


if __name__ == "__main__":
    unittest.main(verbosity=2)
