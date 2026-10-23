import json
from pathlib import Path

import pytest

from testpilot.llm.fake import bundle
from testpilot.schemas.execution import ExecutionResult
from testpilot_wf.agents import GenerationAgent
from testpilot_wf.controller import decide
from testpilot_wf.demo import DemoExecution, DemoGeneration
from testpilot_wf.schemas import Category, Mode
from tests.wf.test_workflow import FixedDiagnosis, run


def test_unknown_evidence_ref_fails_diagnosis(example_root, local_config, tmp_path):
    class BadReference(DemoExecution):
        def diagnose(self, context):
            result = super().diagnose(context)
            result.evidence_refs = ["made-up-proof.json"]
            return result

    state = run(example_root, local_config, tmp_path, execution_client=BadReference())
    assert state.workflow_status == "FAIL" and state.feedback.diagnosis_status == "error"


def test_missing_coverage_cannot_pass(example_root, local_config, tmp_path):
    class NoCoverage:
        def run(self, *args):
            return ExecutionResult(returncode=0, passed=1, collected_test_cases=1)

    state = run(
        example_root,
        local_config,
        tmp_path,
        runner=NoCoverage(),
        execution_client=FixedDiagnosis(Category.PASS),
    )
    assert state.workflow_status == "FAIL" and "coverage" in state.reason


def test_generation_itself_rejects_stale_feedback(example_root, local_config, tmp_path):
    state = run(example_root, local_config, tmp_path)
    state.mode = Mode.REPAIR
    state.feedback.test_version += 1
    from testpilot.errors import LLMOutputValidationError

    with pytest.raises(LLMOutputValidationError, match="Stale"):
        GenerationAgent(local_config, None, DemoGeneration()).invoke(state)


def test_noop_repair_does_not_increment_version(example_root, local_config, tmp_path):
    class NoChange(DemoGeneration):
        def repair(self, context):
            old = json.loads(context)["existing_tests"][0]
            return bundle(old["path"], old["content"])

    state = run(example_root, local_config, tmp_path, "edge_cases", generation_client=NoChange())
    assert state.workflow_status == "FAIL" and state.test_version == 1
    assert "No actual test change" in state.error


def test_repeated_repairs_stop_at_global_budget(example_root, local_config, tmp_path):
    class StillBroken(DemoGeneration):
        def repair(self, context):
            old = json.loads(context)["existing_tests"][0]
            return bundle(old["path"], old["content"] + "\n# attempted import fix\n")

    state = run(example_root, local_config, tmp_path, "edge_cases", generation_client=StillBroken())
    assert state.workflow_status == "FAIL" and "budget" in state.reason
    assert state.repair_count == 2 and state.test_version == 3
    assert len(list((Path(state.run_dir) / "versions").glob("*/execution.json"))) == 3


def test_repeated_improvements_stop_at_budget(example_root, local_config, tmp_path):
    class Insufficient(DemoGeneration):
        count = 0

        def generate(self, context, plan):
            return bundle(
                "test_shipping.py",
                "from shipping import shipping_fee\n"
                "def test_small(): assert shipping_fee(1) == 5\n",
            )

        def improve(self, context):
            self.count += 1
            return bundle(
                f"test_extra_{self.count}.py",
                "from shipping import shipping_fee\n"
                "def test_small(): assert shipping_fee(1) == 5\n",
            )

    state = run(
        example_root, local_config, tmp_path, "edge_cases", generation_client=Insufficient()
    )
    assert state.workflow_status == "FAIL" and "budget" in state.reason
    assert state.coverage_round == 2 and state.test_version == 3


def test_out_of_band_test_change_refused(example_root, local_config, tmp_path):
    state = run(example_root, local_config, tmp_path)
    state.generated_tests[0].content += "\n# illicit mutation\n"
    assert decide(state, local_config)["workflow_status"] == "FAIL"
