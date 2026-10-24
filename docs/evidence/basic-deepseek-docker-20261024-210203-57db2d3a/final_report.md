# TestPilot-WF Run Report

- Mode: Real model mode; see call status
- Status: FINISH
- Reason: Real pytest and required coverage accepted by independent diagnosis
- Test version: 1
- Backend: docker
- Repair / coverage rounds: 0 / 0

```json
{
  "project": "basic",
  "status": "FINISH",
  "demo": false,
  "reason": "Real pytest and required coverage accepted by independent diagnosis",
  "error": null,
  "test_version": 1,
  "repair_rounds": 0,
  "coverage_rounds": 0,
  "execution_backend": "docker",
  "execution": {
    "returncode": 0,
    "stdout": "..............                                                           [100%]\n================================ tests coverage ================================\n_______________ coverage: platform linux, python 3.13.16-final-0 _______________\n\nCoverage JSON written to file .testpilot/coverage.json\n14 passed in 0.49s\n",
    "stderr": "",
    "traceback": "",
    "backend": "docker",
    "timed_out": false,
    "passed": 14,
    "failed": 0,
    "errors": 0,
    "skipped": 0,
    "collected_test_cases": 14,
    "duration_seconds": 1.3785926999989897,
    "warnings": []
  },
  "coverage": {
    "line_coverage": 100.0,
    "branch_coverage": 100.0,
    "missing_lines": {
      "calculator.py": []
    },
    "missing_branches": {
      "calculator.py": []
    }
  },
  "feedback": {
    "failure_category": "PASS",
    "diagnosis": "All 14 collected tests passed with returncode 0, zero failures/errors/skips, and coverage is 100% line and branch (both exceed the 80/70 thresholds). The test suite maps cleanly onto the plan: divide normal quotients (parametrized), zero-divisor ValueError, clamp below/above/within, inclusive bounds, inverted-bounds error, and equal-bounds single-point range. Assertions verify message matching via pytest.raises, and the divide tests additionally check the returned float type. No discrepancies between test intent, source contract, traceback, or coverage are observed.",
    "suggested_action": "PASS",
    "evidence_refs": [
      "versions/001/execution.json",
      "versions/001/coverage.json",
      "versions/001/tests.json"
    ],
    "review_required": false,
    "uncertainty": "Observations are limited to the supplied evidence. The divide float-type assertion only holds incidentally for the chosen integer inputs (Python 3 true division); a bare `assert isinstance(result, float)` would fail on non-float-producing inputs, though current cases are safe. Behavioral intent otherwise fully aligns with source contracts.",
    "test_version": 1,
    "execution_ref": "versions/001/execution.json",
    "coverage_ref": "versions/001/coverage.json",
    "diagnosis_status": "completed"
  },
  "model_calls": [
    {
      "agent": "generation",
      "task": "PLAN",
      "attempt": 1,
      "model": "deepseek-flash",
      "max_tokens": 50000,
      "context_chars": 1657,
      "status": "completed",
      "response_chars": 3294
    },
    {
      "agent": "generation",
      "task": "GENERATE",
      "attempt": 1,
      "model": "deepseek-flash",
      "max_tokens": 50000,
      "context_chars": 4984,
      "status": "completed",
      "response_chars": 1426
    },
    {
      "agent": "execution",
      "task": "DIAGNOSE",
      "attempt": 1,
      "model": "deepseek-flash",
      "max_tokens": 50000,
      "context_chars": 7474,
      "status": "completed",
      "response_chars": 1125
    }
  ],
  "config": {
    "llm": {
      "provider": "deepseek",
      "model": "deepseek-flash",
      "max_retries": 2,
      "timeout_seconds": 60.0,
      "max_tokens": 50000
    },
    "execution": {
      "preferred_runner": "docker",
      "allow_local_fallback": false,
      "timeout_seconds": 30.0,
      "install_dependencies": false,
      "install_timeout_seconds": 180.0,
      "docker_image": "testpilot-runner:latest"
    },
    "agent": {
      "max_repair_rounds": 2,
      "context_max_chars": 100000
    },
    "coverage": {
      "enabled": true,
      "line_threshold": 80,
      "branch_threshold": 70,
      "max_improvement_rounds": 2
    }
  },
  "limitations": [
    "Snapshots are evidence, not resumable checkpoints",
    "Only generated tests execute; original test suite is preserved",
    "Static preflight is not a security sandbox; Local is for trusted code",
    "Assertion preservation is conservative, not proof of semantic correctness"
  ]
}
```
