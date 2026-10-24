# TestPilot-WF Run Report

- Mode: Real model mode; see call status
- Status: FINISH
- Reason: Real pytest and required coverage accepted by independent diagnosis
- Test version: 1
- Backend: docker
- Repair / coverage rounds: 0 / 0

```json
{
  "project": "edge_cases",
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
    "stdout": "...................                                                      [100%]\n================================ tests coverage ================================\n_______________ coverage: platform linux, python 3.13.16-final-0 _______________\n\nCoverage JSON written to file .testpilot/coverage.json\n19 passed in 0.33s\n",
    "stderr": "",
    "traceback": "",
    "backend": "docker",
    "timed_out": false,
    "passed": 19,
    "failed": 0,
    "errors": 0,
    "skipped": 0,
    "collected_test_cases": 19,
    "duration_seconds": 1.0473282000166364,
    "warnings": []
  },
  "coverage": {
    "line_coverage": 100.0,
    "branch_coverage": 100.0,
    "missing_lines": {
      "shipping.py": []
    },
    "missing_branches": {
      "shipping.py": []
    }
  },
  "feedback": {
    "failure_category": "PASS",
    "diagnosis": "All 19 collected test cases passed with zero failures, errors, or skips (execution.json: returncode 0, 19 passed). Coverage is 100% line and 100% branch on shipping.py, well above the 80% line / 70% branch thresholds, with no missing lines or branches. The test suite independently exercises the raise-nonpositive exception path (both express values), both upper-tier boundaries (1 and 5 inclusive plus epsilon above each), interior representatives of all three tiers, express flat surcharge across tiers, express-preserves-tier at boundaries, and the default-express=False behavior — matching the source contract in shipping_fee. Independent quality observation: epsilon values (1.0001, 5.0001) are reasonable stand-ins for 'just above' but are not guaranteed minimal crossings for all float representations; a strict reviewer might prefer math.nextafter for exact threshold adjacency. This is a minor robustness suggestion only and does not affect the current green result. No evidence of test generation errors, source contract inconsistencies, or environment issues.",
    "suggested_action": "PASS",
    "evidence_refs": [
      "versions/001/tests.json",
      "versions/001/execution.json",
      "versions/001/coverage.json"
    ],
    "review_required": false,
    "uncertainty": "None material. The only residual concern is that boundary-adjacent values use fixed epsilon literals rather than exact next-representable floats; this does not weaken the passing verdict because actual source comparisons use <= on the same literals tested.",
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
      "context_chars": 1178,
      "status": "completed",
      "response_chars": 3952
    },
    {
      "agent": "generation",
      "task": "GENERATE",
      "attempt": 1,
      "model": "deepseek-flash",
      "max_tokens": 50000,
      "context_chars": 5163,
      "status": "completed",
      "response_chars": 1602
    },
    {
      "agent": "execution",
      "task": "DIAGNOSE",
      "attempt": 1,
      "model": "deepseek-flash",
      "max_tokens": 50000,
      "context_chars": 7807,
      "status": "completed",
      "response_chars": 1538
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
