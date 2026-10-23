from testpilot_wf.schemas import Category, Mode
from testpilot_wf.validation import digest


def decide(state, config):
    def end(status, reason):
        return {"workflow_status": status, "route": "end", "reason": reason}

    if state.error:
        return end("FAIL", state.error)
    feedback = state.feedback
    if not feedback or feedback.test_version != state.test_version:
        return end("FAIL", "Missing or stale feedback")
    if digest(state.generated_tests) != state.test_digest:
        return end("FAIL", "Tests changed outside generation commit")
    if not state.messages or state.messages[-1].payload != feedback:
        return end("FAIL", "Feedback does not match latest validated message")
    category = feedback.failure_category
    if feedback.diagnosis_status != "completed" or category == Category.DIAGNOSIS:
        return end("FAIL", "Execution diagnosis failed")
    if feedback.review_required or category in (Category.SOURCE, Category.REVIEW):
        return end("REVIEW_REQUIRED", feedback.diagnosis)
    if category == Category.ENVIRONMENT:
        return end("FAIL", "Execution environment error; no automatic Local fallback")
    result = state.execution_result
    if result is None:
        return end("FAIL", "No real execution observation")
    if result.timed_out or result.returncode in (3, 4, 5) or result.returncode < 0:
        return end("FAIL", "Timeout, collection or runner failure")
    failed = result.returncode != 0 or result.failed > 0 or result.errors > 0
    if failed:
        if category != Category.REPAIR:
            return end("REVIEW_REQUIRED", "Diagnosis conflicts with actual pytest failure")
        if not result.traceback:
            return end("REVIEW_REQUIRED", "Repair requires real failure evidence")
        if state.repair_count >= config.agent.max_repair_rounds:
            return end("FAIL", "Repair budget exhausted")
        return {"mode": Mode.REPAIR, "repair_count": state.repair_count + 1, "route": "generation"}
    if result.passed <= 0 or not result.collected_test_cases:
        return end("FAIL", "No actual passed/collected tests")
    if config.coverage.enabled:
        if state.coverage is None:
            return end("FAIL", "Required coverage evidence missing")
        low = (
            state.coverage.line_coverage < config.coverage.line_threshold
            or state.coverage.branch_coverage < config.coverage.branch_threshold
        )
        if low:
            if category not in (Category.PASS, Category.IMPROVE):
                return end("REVIEW_REQUIRED", "Diagnosis inconsistent with coverage evidence")
            if state.coverage_round >= config.coverage.max_improvement_rounds:
                return end("FAIL", "Coverage improvement budget exhausted")
            return {
                "mode": Mode.IMPROVE,
                "coverage_round": state.coverage_round + 1,
                "route": "generation",
            }
    if category != Category.PASS:
        return end("REVIEW_REQUIRED", "Diagnosis does not approve the observed test suite")
    return end("FINISH", "Real pytest and required coverage accepted by independent diagnosis")
