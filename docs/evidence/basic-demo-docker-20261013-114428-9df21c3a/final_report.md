# TestPilot-WF Run Report

- Mode: DEMO (no LLM calls)
- Status: FINISH
- Reason: Real pytest and required coverage accepted by independent diagnosis
- Test version: 1
- Backend: docker
- Repair / coverage rounds: 0 / 0

```json
{
  "project": "basic",
  "status": "FINISH",
  "demo": true,
  "reason": "Real pytest and required coverage accepted by independent diagnosis",
  "error": null,
  "test_version": 1,
  "repair_rounds": 0,
  "coverage_rounds": 0,
  "execution_backend": "docker",
  "execution": {
    "returncode": 0,
    "stdout": ".......                                                                  [100%]\n================================ tests coverage ================================\n_______________ coverage: platform linux, python 3.13.16-final-0 _______________\n\nCoverage JSON written to file .testpilot/coverage.json\n7 passed in 0.38s\n",
    "stderr": "",
    "traceback": "",
    "backend": "docker",
    "timed_out": false,
    "passed": 7,
    "failed": 0,
    "errors": 0,
    "skipped": 0,
    "collected_test_cases": 7,
    "duration_seconds": 1.129666700027883,
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
    "diagnosis": "DEMO scripted diagnosis: PASS; inspect referenced tool facts",
    "suggested_action": "PASS",
    "evidence_refs": [
      "versions/001/tests.json",
      "versions/001/execution.json",
      "versions/001/coverage.json"
    ],
    "review_required": false,
    "uncertainty": "Fixed demo response, not real LLM reasoning",
    "test_version": 1,
    "execution_ref": "versions/001/execution.json",
    "coverage_ref": "versions/001/coverage.json",
    "diagnosis_status": "completed"
  },
  "model_calls": [],
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
      "line_threshold": 80.0,
      "branch_threshold": 70.0,
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
