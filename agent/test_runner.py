"""
test_runner.py
---------------
Milestone 4 -- "Perform End-to-End Testing" subtopic, made real and
in-app rather than only a static document.

Runs the project's real automated test suite
(tests/test_milestone4.py) as a subprocess, parses pytest's verbose
output into per-test and per-category results, and persists the run to
the new test_runs table so the Testing Center page
(/testing-center) can show live, re-runnable, historical test results
-- not a hardcoded "all tests pass" claim.
"""

import json
import re
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TEST_FILE = "tests/test_milestone4.py"

# Maps each automated test id to the testing category it satisfies, for
# the Milestone 4 brief's required categories (Functional, Integration,
# AI/Agent, API, Workflow, Dashboard, Performance, Security, Error
# Handling, User Acceptance).
CATEGORY_MAP = {
    "test_01_functional_m1_m2_m3_routes_return_200": "Functional",
    "test_02_functional_m4_routes_return_200": "Functional",
    "test_03_integration_intelligence_engine_reflects_live_attendee_count": "Integration",
    "test_04_integration_shared_database_across_milestones": "Integration",
    "test_05_agent_incident_classification_high_risk_keyword_escalates": "AI / Agent",
    "test_06_agent_incident_imminent_session_boosts_priority": "AI / Agent",
    "test_07_agent_sponsorship_scoring_is_explainable": "AI / Agent",
    "test_08_agent_intelligence_engine_score_bounds": "AI / Agent",
    "test_09_api_endpoints_return_valid_json": "API",
    "test_10_api_intelligence_engine_shape": "API",
    "test_11_workflow_speaker_cancellation_end_to_end": "Workflow / Orchestration",
    "test_12_workflow_invalid_session_id_handled_gracefully": "Workflow / Orchestration",
    "test_13_dashboard_executive_data_is_live_not_hardcoded": "Dashboard",
    "test_14_performance_executive_dashboard_responds_quickly": "Performance",
    "test_15_performance_intelligence_engine_cache_reduces_repeat_calls": "Performance",
    "test_16_security_orchestration_rejects_missing_session_id": "Security",
    "test_17_security_sql_injection_style_search_input_is_safe": "Security",
    "test_18_error_handling_unknown_route_returns_404": "Error Handling",
    "test_19_error_handling_orchestration_bad_session_id_type": "Error Handling",
    "test_20_uat_full_event_lifecycle_scenario": "User Acceptance",
    "test_21_testing_center_page_and_api_render": "Functional",
    "test_22_production_readiness_report_is_live": "Functional",
    "test_23_all_five_m4_subtopics_reachable_via_nav": "Functional",
}

TEST_LINE_RE = re.compile(r"::(test_\S+?)\s+(PASSED|FAILED|ERROR|SKIPPED)")
SUMMARY_RE = re.compile(
    r"(\d+) passed(?:, (\d+) failed)?(?:, (\d+) error\w*)? in ([\d.]+)s"
)


def run_test_suite(triggered_by="Manual"):
    """Actually executes `python -m pytest tests/test_milestone4.py -v`
    as a subprocess against the real project, parses the results, and
    persists them via database.insert_test_run(). Returns the parsed
    summary dict. Import database lazily to avoid a circular import
    (database.py does not import this module)."""
    import database

    start = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", TEST_FILE, "-v", "--tb=short"],
            cwd=str(BASE_DIR), capture_output=True, text=True, timeout=120,
        )
        output = proc.stdout + "\n" + proc.stderr
    except Exception as exc:  # pragma: no cover - defensive
        output = f"Test runner failed to execute: {exc}"
        proc = None

    duration = round(time.time() - start, 2)

    per_test = {}
    for match in TEST_LINE_RE.finditer(output):
        test_id, status = match.group(1), match.group(2)
        per_test[test_id] = status

    summary_match = SUMMARY_RE.search(output)
    if summary_match:
        passed = int(summary_match.group(1) or 0)
        failed = int(summary_match.group(2) or 0)
        errors = int(summary_match.group(3) or 0)
        duration = float(summary_match.group(4))
    else:
        passed = list(per_test.values()).count("PASSED")
        failed = list(per_test.values()).count("FAILED")
        errors = list(per_test.values()).count("ERROR")
    total = passed + failed + errors

    category_results = {}
    for test_id, status in per_test.items():
        category = CATEGORY_MAP.get(test_id, "Other")
        bucket = category_results.setdefault(category, {"passed": 0, "failed": 0, "total": 0})
        bucket["total"] += 1
        if status == "PASSED":
            bucket["passed"] += 1
        else:
            bucket["failed"] += 1

    database.insert_test_run(
        total=total, passed=passed, failed=failed, errors=errors,
        duration_seconds=duration, category_json=json.dumps(category_results),
        raw_output=output[-8000:],  # keep the log bounded
        triggered_by=triggered_by,
    )

    return {
        "total": total, "passed": passed, "failed": failed, "errors": errors,
        "duration_seconds": duration, "category_results": category_results,
        "per_test": per_test, "raw_output": output,
        "ok": (proc is not None and proc.returncode == 0),
    }
