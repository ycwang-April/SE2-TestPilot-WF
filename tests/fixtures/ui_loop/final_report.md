# TestPilot-WF Run Report

- Mode: DEMO (no LLM calls)
- Status: FINISH
- Reason: Real pytest and required coverage accepted by independent diagnosis
- Test version: 3
- Backend: docker
- Repair / coverage rounds: 1 / 1

```json
{
  "project": "edge_cases",
  "status": "FINISH",
  "demo": true,
  "reason": "Real pytest and required coverage accepted by independent diagnosis",
  "error": null,
  "test_version": 3,
  "repair_rounds": 1,
  "coverage_rounds": 1,
  "execution_backend": "docker",
  "execution": {
    "returncode": 0,
    "stdout": ".........                                                                [100%]\n================================ tests coverage ================================\n_______________ coverage: platform linux, python 3.13.16-final-0 _______________\n\nCoverage JSON written to file .testpilot/coverage.json\n9 passed in 0.33s\n",
    "stderr": "",
    "traceback": "",
    "backend": "docker",
    "timed_out": false,
    "passed": 9,
    "failed": 0,
    "errors": 0,
    "skipped": 0,
    "collected_test_cases": 9,
    "duration_seconds": 0.878050799947232,
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
    "diagnosis": "DEMO scripted diagnosis: PASS; inspect referenced tool facts",
    "suggested_action": "PASS",
    "evidence_refs": [
      "versions/003/tests.json",
      "versions/003/execution.json",
      "versions/003/coverage.json"
    ],
    "review_required": false,
    "uncertainty": "Fixed demo response, not real LLM reasoning",
    "test_version": 3,
    "execution_ref": "versions/003/execution.json",
    "coverage_ref": "versions/003/coverage.json",
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
