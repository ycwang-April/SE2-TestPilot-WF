import json
from pathlib import Path

import pytest

from testpilot.reporting.artifacts import ArtifactWriter
from testpilot.tools.context_selector import ContextSelector
from testpilot_wf.agents import ExecutionAgent
from testpilot_wf.demo import DemoExecution
from testpilot_wf.schemas import Category
from tests.wf.test_workflow import run


class CapturingExecution(DemoExecution):
    def __init__(self):
        self.contexts = []

    def diagnose(self, context):
        self.contexts.append(context)
        return super().diagnose(context)


@pytest.mark.parametrize("example", ["basic", "edge_cases"])
def test_diagnosis_task_and_all_selected_evidence(example_root, local_config, tmp_path, example):
    client = CapturingExecution()
    state = run(example_root, local_config, tmp_path, example, execution_client=client)
    assert state.workflow_status == "FINISH", state.reason
    expected = (
        [Category.PASS]
        if example == "basic"
        else [Category.REPAIR, Category.IMPROVE, Category.PASS]
    )
    assert len(client.contexts) == len(expected)
    directory = Path(state.run_dir)
    for version, (serialized, category) in enumerate(
        zip(client.contexts, expected, strict=True), 1
    ):
        context = json.loads(serialized)
        assert context["action"] == "DIAGNOSE"
        assert len(serialized) <= local_config.agent.context_max_chars
        assert context["test_version"] == version
        generation, execution = state.messages[2 * (version - 1) : 2 * version]
        assert execution.payload.failure_category == category
        assert context["test_plan"] == [p.model_dump() for p in generation.payload.test_plan]
        assert context["existing_tests"] == json.loads(
            (directory / generation.payload.tests_ref).read_text(encoding="utf-8")
        )
        raw = json.loads((directory / execution.payload.execution_ref).read_text(encoding="utf-8"))
        result = raw["result"]
        result.pop(
            "coverage_data", None
        )  # Existing selector excludes only the raw coverage payload.
        assert context["execution"] == result
        assert context["environment_error"] == raw["environment_error"]
        assert context["coverage"] == json.loads(
            (directory / execution.payload.coverage_ref).read_text(encoding="utf-8")
        )
        assert context["coverage_policy"] == local_config.coverage.model_dump()
        assert context["source"] and context["ast"] and context["targets"] == state.target_modules
        assert context["evidence_refs"] == execution.evidence_refs
        assert set(execution.payload.evidence_refs).issubset(context["evidence_refs"])
        assert all((directory / ref).is_file() for ref in context["evidence_refs"])
        if category == Category.REPAIR:
            assert result["returncode"] != 0 and "ImportError" in result["traceback"]
        elif category == Category.IMPROVE:
            assert result["returncode"] == 0
            assert context["coverage"]["line_coverage"] < local_config.coverage.line_threshold
        else:
            assert result["passed"] > 0 and result["returncode"] == 0


@pytest.mark.parametrize("boundary", ["selector", "diagnosis_envelope"])
def test_diagnosis_context_budgets_keep_raw_facts_and_skip_model(
    example_root, local_config, tmp_path, boundary
):
    state = run(example_root, local_config, tmp_path)
    state.messages = state.messages[:1]  # The committed Generation envelope entering Execution.
    selected = ContextSelector(local_config.agent.context_max_chars).select(
        state, "IMPROVE_COVERAGE", state.target_modules
    )
    budget = len(selected) - (1 if boundary == "selector" else 0)
    assert budget >= 2000
    local_config.agent.context_max_chars = budget
    client = CapturingExecution()

    class Runner:
        def run(self, *args):
            return state.execution_result.model_copy(deep=True)

    directory = tmp_path / boundary
    updates = ExecutionAgent(local_config, ArtifactWriter(directory), Runner(), client).invoke(
        state
    )
    assert client.contexts == []
    assert updates["feedback"].failure_category == Category.DIAGNOSIS
    assert updates["feedback"].diagnosis_status == "error"
    assert updates["execution_result"] == state.execution_result
    assert updates["coverage"] == state.coverage
    raw = json.loads((directory / "versions/001/execution.json").read_text(encoding="utf-8"))
    assert raw["result"] == state.execution_result.model_dump()
    assert (directory / "versions/001/feedback.json").is_file()
