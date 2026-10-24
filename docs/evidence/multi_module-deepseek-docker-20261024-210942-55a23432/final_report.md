# TestPilot-WF Run Report

- Mode: Real model mode; see call status
- Status: FINISH
- Reason: Real pytest and required coverage accepted by independent diagnosis
- Test version: 1
- Backend: docker
- Repair / coverage rounds: 0 / 0

```json
{
  "project": "multi_module",
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
    "stdout": "................................................                         [100%]\n================================ tests coverage ================================\n_______________ coverage: platform linux, python 3.13.16-final-0 _______________\n\nCoverage JSON written to file .testpilot/coverage.json\n48 passed in 0.46s\n",
    "stderr": "",
    "traceback": "",
    "backend": "docker",
    "timed_out": false,
    "passed": 48,
    "failed": 0,
    "errors": 0,
    "skipped": 0,
    "collected_test_cases": 48,
    "duration_seconds": 1.170703699986916,
    "warnings": []
  },
  "coverage": {
    "line_coverage": 100.0,
    "branch_coverage": 100.0,
    "missing_lines": {
      "discount.py": [],
      "models.py": [],
      "order.py": []
    },
    "missing_branches": {
      "discount.py": [],
      "models.py": [],
      "order.py": []
    }
  },
  "feedback": {
    "failure_category": "PASS",
    "diagnosis": "All 48 collected tests passed with returncode 0 (0 failures, 0 errors, 0 skips) in 0.46s. Line and branch coverage both hit 100% across discount.py, models.py, and order.py, with no missing lines or branches. Test intent maps cleanly onto source contracts: discount_rate member precedence (0.2 for members regardless of total), inclusive >=100 threshold for non-members (0.1), sub-threshold zero rate, and ValueError on negative totals; Item.subtotal validates negatives at call time and returns price*quantity; order_total sums subtotals, applies discount, and rounds to two decimals. Boundary cases (exact 100.0, 99.99 vs 100.01, default quantity, zero values, mutated negative quantity) are independently and meaningfully covered rather than trivially duplicated.",
    "suggested_action": "PASS",
    "evidence_refs": [
      "versions/001/tests.json",
      "versions/001/execution.json",
      "versions/001/coverage.json"
    ],
    "review_required": false,
    "uncertainty": "None material. Coverage is complete and tests are behaviorally distinct. Minor untested edge: order_total with an all-zero-subtotal negative path via discount_rate is not directly exercised, but discount_rate's negative guard and Item validation are each independently covered, so residual risk is negligible.",
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
      "context_chars": 1108,
      "status": "completed",
      "response_chars": 3277
    },
    {
      "agent": "generation",
      "task": "PLAN",
      "attempt": 1,
      "model": "deepseek-flash",
      "max_tokens": 50000,
      "context_chars": 4532,
      "status": "completed",
      "response_chars": 4058
    },
    {
      "agent": "generation",
      "task": "PLAN",
      "attempt": 1,
      "model": "deepseek-flash",
      "max_tokens": 50000,
      "context_chars": 10435,
      "status": "completed",
      "response_chars": 5034
    },
    {
      "agent": "generation",
      "task": "GENERATE",
      "attempt": 1,
      "model": "deepseek-flash",
      "max_tokens": 50000,
      "context_chars": 13840,
      "status": "completed",
      "response_chars": 1681
    },
    {
      "agent": "generation",
      "task": "GENERATE",
      "attempt": 1,
      "model": "deepseek-flash",
      "max_tokens": 50000,
      "context_chars": 15513,
      "status": "completed",
      "response_chars": 2164
    },
    {
      "agent": "generation",
      "task": "GENERATE",
      "attempt": 1,
      "model": "deepseek-flash",
      "max_tokens": 50000,
      "context_chars": 19331,
      "status": "completed",
      "response_chars": 2124
    },
    {
      "agent": "execution",
      "task": "DIAGNOSE",
      "attempt": 1,
      "model": "deepseek-flash",
      "max_tokens": 50000,
      "context_chars": 22567,
      "status": "completed",
      "response_chars": 1287
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
