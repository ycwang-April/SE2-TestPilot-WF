import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from testpilot.errors import DockerUnavailableError
from testpilot.llm.fake import bundle
from testpilot.schemas.execution import ExecutionResult
from testpilot_wf.demo import DemoExecution, DemoGeneration
from testpilot_wf.schemas import AgentMessage, Category, Diagnosis, Mode
from testpilot_wf.service import run_project
from testpilot_wf.workflow import AgentRegistry, WorkflowBuilder


def run(example_root, local_config, tmp_path, example="basic", **kwargs):
    return run_project(
        example_root / example, config=local_config, demo=True, output=tmp_path / "runs", **kwargs
    )


def test_case_a_independent_agents(example_root, local_config, tmp_path):
    class Generation(DemoGeneration):
        def generate(self, context, plan):
            self.called = True
            return super().generate(context, plan)

    class Execution(DemoExecution):
        def diagnose(self, context):
            self.context = json.loads(context)
            return super().diagnose(context)

    generation, execution = Generation(), Execution()
    before = (example_root / "basic/calculator.py").read_bytes()
    state = run(
        example_root,
        local_config,
        tmp_path,
        generation_client=generation,
        execution_client=execution,
    )
    assert state.workflow_status == "FINISH", state.reason
    assert generation.called and execution.context["execution"]["passed"] > 0
    assert execution.context["action"] == "DIAGNOSE"
    assert [m.sender for m in state.messages] == ["generation", "execution"]
    assert state.test_version == 1 and state.execution_result.collected_test_cases > 0
    assert [event["agent"] for event in state.trace] == ["generation", "execution", "controller"]
    assert (example_root / "basic/calculator.py").read_bytes() == before
    assert json.loads((Path(state.run_dir) / "final_report.json").read_text(encoding="utf-8"))[
        "demo"
    ]


def test_cases_b_c_feedback_and_real_reexecution(example_root, local_config, tmp_path):
    state = run(example_root, local_config, tmp_path, "edge_cases")
    assert state.workflow_status == "FINISH", state.reason
    assert state.repair_count == state.coverage_round == 1
    assert state.test_version == 3 and state.execution_result.passed == 9
    assert [m.test_version for m in state.messages] == [1, 1, 2, 2, 3, 3]
    assert [m.payload.mode for m in state.messages if m.sender == "generation"] == list(Mode)
    root = Path(state.run_dir)
    first = json.loads((root / "versions/001/execution.json").read_text(encoding="utf-8"))["result"]
    assert first["returncode"] != 0 and "ImportError" in first["traceback"]
    assert state.coverage.line_coverage == state.coverage.branch_coverage == 100
    # Repair changes only import; original assertion is retained exactly.
    assert "assert shipping_fe(1) == 5" in state.generated_tests[0].content


@pytest.mark.parametrize("budget", ["repair", "coverage"])
def test_case_d_budget_report(example_root, local_config, tmp_path, budget):
    if budget == "repair":
        local_config.agent.max_repair_rounds = 0
    else:
        local_config.coverage.max_improvement_rounds = 0
    state = run(example_root, local_config, tmp_path, "edge_cases")
    assert state.workflow_status == "FAIL" and "budget" in state.reason
    assert (Path(state.run_dir) / "final_report.md").exists()


class FixedDiagnosis:
    def __init__(self, category):
        self.category = category

    def diagnose(self, context):
        return Diagnosis(
            failure_category=self.category,
            suggested_action=self.category,
            diagnosis="Test diagnosis",
            evidence_refs=json.loads(context)["evidence_refs"],
            review_required=self.category in (Category.SOURCE, Category.REVIEW),
            uncertainty="Test stub",
        )


@pytest.mark.parametrize("category", [Category.SOURCE, Category.REVIEW])
def test_source_bug_stops_without_repair(example_root, local_config, tmp_path, category):
    state = run(
        example_root,
        local_config,
        tmp_path,
        "edge_cases",
        execution_client=FixedDiagnosis(category),
    )
    assert state.workflow_status == "REVIEW_REQUIRED" and state.repair_count == 0
    assert state.execution_result.returncode != 0


def test_llm_pass_cannot_hide_pytest_failure(example_root, local_config, tmp_path):
    state = run(
        example_root,
        local_config,
        tmp_path,
        "edge_cases",
        execution_client=FixedDiagnosis(Category.PASS),
    )
    assert state.workflow_status == "REVIEW_REQUIRED"


def test_llm_pass_cannot_hide_low_coverage(example_root, local_config, tmp_path):
    class LowGeneration(DemoGeneration):
        def generate(self, context, plan):
            return bundle(
                "test_shipping.py",
                "from shipping import shipping_fee\n"
                "def test_regular_small(): assert shipping_fee(1) == 5\n",
            )

    state = run(
        example_root,
        local_config,
        tmp_path,
        "edge_cases",
        generation_client=LowGeneration(),
        execution_client=FixedDiagnosis(Category.PASS),
    )
    assert state.workflow_status == "FINISH" and state.coverage_round == 1


def test_diagnosis_failure_keeps_raw_facts(example_root, local_config, tmp_path):
    class Invalid:
        def diagnose(self, context):
            return {"bad": "format"}

    state = run(example_root, local_config, tmp_path, execution_client=Invalid())
    assert state.workflow_status == "FAIL"
    assert state.feedback.failure_category == Category.DIAGNOSIS
    assert state.execution_result.passed > 0
    assert (Path(state.run_dir) / "versions/001/execution.json").exists()


def test_environment_never_falls_back(example_root, local_config, tmp_path):
    class MissingDocker:
        def run(self, *args):
            raise DockerUnavailableError("missing daemon")

    state = run(example_root, local_config, tmp_path, runner=MissingDocker())
    assert state.workflow_status == "FAIL"
    assert state.feedback.failure_category == Category.ENVIRONMENT
    assert state.execution_result is None


@pytest.mark.parametrize(
    "result",
    [
        ExecutionResult(returncode=0, passed=0, skipped=3, collected_test_cases=3),
        ExecutionResult(returncode=0, passed=1, collected_test_cases=0),
        ExecutionResult(returncode=0, passed=1, collected_test_cases=None),
        ExecutionResult(returncode=0, passed=1, collected_test_cases=1, timed_out=True),
        ExecutionResult(returncode=5),
    ],
)
def test_invalid_execution_never_finishes(example_root, local_config, tmp_path, result):
    class Runner:
        def run(self, *args):
            return result

    local_config.coverage.enabled = False
    state = run(
        example_root,
        local_config,
        tmp_path,
        runner=Runner(),
        execution_client=FixedDiagnosis(Category.PASS),
    )
    assert state.workflow_status == "FAIL"


def test_mock_agent_real_graph_extension(example_root, local_config, tmp_path):
    class MockAgent:
        name = "audit"
        writes = {"extensions"}

        def invoke(self, state):
            return {"extensions": {"seen_version": state.test_version, "digest": state.test_digest}}

    state = run(
        example_root,
        local_config,
        tmp_path,
        extra_agents=[MockAgent()],
        chain=("generation", "audit", "execution"),
    )
    assert state.workflow_status == "FINISH"
    assert state.extensions == {"seen_version": 1, "digest": state.test_digest}
    assert [e["agent"] for e in state.trace] == ["generation", "audit", "execution", "controller"]


def test_registry_and_invalid_graph():
    class Agent:
        name = "generation"

    registry = AgentRegistry().register(Agent())
    with pytest.raises(ValueError):
        registry.register(Agent())
    replacement = Agent()
    registry.register(replacement, replace=True)
    assert registry.get("generation") is replacement
    with pytest.raises(KeyError):
        WorkflowBuilder(registry)
    with pytest.raises(ValueError):
        WorkflowBuilder(registry, ("generation", "generation", "execution"))


def test_envelope_validation(example_root, local_config, tmp_path):
    state = run(example_root, local_config, tmp_path)
    message = state.messages[0].model_dump()
    for field, value in [("test_version", 99), ("sender", "execution"), ("extra", 1)]:
        with pytest.raises(ValidationError):
            AgentMessage.model_validate({**message, field: value})


def test_stale_feedback_controller(example_root, local_config, tmp_path):
    from testpilot_wf.controller import decide

    state = run(example_root, local_config, tmp_path)
    state.feedback.test_version += 1
    assert decide(state, local_config)["workflow_status"] == "FAIL"


def test_rejected_candidate_does_not_commit_version(example_root, local_config, tmp_path):
    class BadRepair(DemoGeneration):
        def repair(self, context):
            return bundle(
                "test_shipping.py",
                "from shipping import shipping_fee as shipping_fe\n"
                "def test_regular_small(): assert shipping_fe(1) >= 0\n",
            )

    state = run(example_root, local_config, tmp_path, "edge_cases", generation_client=BadRepair())
    assert state.workflow_status == "FAIL" and state.test_version == 1
    assert "== 5" in state.generated_tests[0].content
    assert list((Path(state.run_dir) / "rejected").glob("*.json"))


def test_extension_cannot_change_tests(example_root, local_config, tmp_path):
    class BadAgent:
        name = "bad"
        writes = {"test_version"}

        def invoke(self, state):
            return {"test_version": 9}

    state = run(
        example_root,
        local_config,
        tmp_path,
        extra_agents=[BadAgent()],
        chain=("generation", "bad", "execution"),
    )
    assert state.workflow_status == "FAIL" and state.test_version == 1


class MockAuditAgent:
    writes = {"extensions"}

    def __init__(self, name="audit"):
        self.name = name

    def invoke(self, state):
        visit = {
            "agent": self.name,
            "version": state.test_version,
            "digest": state.test_digest,
            "feedback": state.feedback.model_dump() if state.feedback else None,
            "last_message": state.messages[-1].model_dump(),
        }
        return {"extensions": {"visits": [*state.extensions.get("visits", []), visit]}}


@pytest.mark.parametrize(
    "chain",
    [
        ("generation", "audit", "execution"),
        ("generation", "execution", "audit"),
        ("generation", "before", "execution", "after"),
    ],
)
@pytest.mark.parametrize("example", ["basic", "edge_cases"])
def test_extensions_follow_chain_and_preserve_feedback(
    example_root, local_config, tmp_path, chain, example
):
    agents = [MockAuditAgent(name) for name in chain if name not in {"generation", "execution"}]
    state = run(example_root, local_config, tmp_path, example, extra_agents=agents, chain=chain)
    rounds = 1 if example == "basic" else 3
    assert state.workflow_status == "FINISH", state.reason
    assert state.test_version == rounds
    assert state.repair_count == state.coverage_round == (rounds - 1) // 2
    assert [event["agent"] for event in state.trace] == [*chain, "controller"] * rounds
    assert [m.sender for m in state.messages] == ["generation", "execution"] * rounds
    assert [m.sequence for m in state.messages] == list(range(1, rounds * 2 + 1))
    assert [m.test_version for m in state.messages] == [
        v for v in range(1, rounds + 1) for _ in (0, 1)
    ]
    for visit in state.extensions["visits"]:
        version = visit["version"]
        generation, execution = state.messages[2 * (version - 1) : 2 * version]
        assert visit["digest"] == generation.payload.digest
        after_execution = chain.index(visit["agent"]) > chain.index("execution")
        expected = execution if after_execution else generation
        assert visit["last_message"] == expected.model_dump()
        if after_execution:
            assert visit["feedback"] == execution.payload.model_dump()
        else:
            previous = state.messages[2 * version - 3].payload.model_dump() if version > 1 else None
            assert visit["feedback"] == previous
    audit_events = [
        event
        for event in state.trace
        if event["agent"] not in {"generation", "execution", "controller"}
    ]
    assert len(audit_events) == len(agents) * rounds
    assert all(
        event["task"] == "EXTENSION" and not event["output_messages"] for event in audit_events
    )
    assert state.messages[-1].payload == state.feedback


@pytest.mark.parametrize("budget", ["repair", "coverage"])
def test_post_extension_respects_controller_budget(example_root, local_config, tmp_path, budget):
    if budget == "repair":
        local_config.agent.max_repair_rounds = 0
    else:
        local_config.coverage.max_improvement_rounds = 0
    state = run(
        example_root,
        local_config,
        tmp_path,
        "edge_cases",
        extra_agents=[MockAuditAgent()],
        chain=("generation", "execution", "audit"),
    )
    rounds = 1 if budget == "repair" else 2
    assert state.workflow_status == "FAIL" and "budget" in state.reason
    assert state.test_version == rounds and state.coverage_round == 0
    assert len(state.extensions["visits"]) == rounds
    assert [event["agent"] for event in state.trace] == [
        "generation",
        "execution",
        "audit",
        "controller",
    ] * rounds


@pytest.mark.parametrize(
    "field,value",
    [
        ("generated_tests", []),
        ("test_version", 9),
        ("test_digest", "forged"),
        ("messages", []),
        ("feedback", None),
        ("execution_result", None),
        ("coverage", None),
        ("repair_count", 9),
        ("coverage_round", 9),
        ("route", "generation"),
        ("workflow_status", "FINISH"),
    ],
)
def test_post_extension_cannot_update_protected_fields(
    example_root, local_config, tmp_path, field, value
):
    class Forbidden(MockAuditAgent):
        writes = {field, "extensions"}

        def invoke(self, state):
            # Even nested in-place changes affect only the wrapper's private copy.
            state.feedback.diagnosis = "forged"
            state.messages.clear()
            state.generated_tests.clear()
            return {field: value}

    state = run(
        example_root,
        local_config,
        tmp_path,
        extra_agents=[Forbidden()],
        chain=("generation", "execution", "audit"),
    )
    assert state.workflow_status == "FAIL" and state.failure_stage == "audit"
    assert state.test_version == 1 and state.repair_count == state.coverage_round == 0
    assert len(state.messages) == 2 and state.messages[-1].payload == state.feedback
    assert "forged" not in state.feedback.diagnosis
    assert state.execution_result.passed > 0 and state.coverage is not None
    assert state.generated_tests and state.test_digest == state.generation.digest
    assert [event["agent"] for event in state.trace] == [
        "generation",
        "execution",
        "audit",
        "controller",
    ]


@pytest.mark.parametrize("position", ["before", "after"])
def test_extension_exception_routes_directly_to_controller(
    example_root, local_config, tmp_path, position
):
    class Broken(MockAuditAgent):
        def invoke(self, state):
            raise RuntimeError("test extension failure")

    chain = (
        ("generation", "audit", "execution")
        if position == "before"
        else ("generation", "execution", "audit")
    )
    state = run(example_root, local_config, tmp_path, extra_agents=[Broken()], chain=chain)
    assert state.workflow_status == "FAIL" and state.failure_stage == "audit"
    expected = (
        ["generation", "audit", "controller"] if position == "before" else [*chain, "controller"]
    )
    assert [event["agent"] for event in state.trace] == expected
    assert state.test_version == 1 and state.repair_count == state.coverage_round == 0


@pytest.mark.parametrize(
    "chain,error",
    [
        ((), ValueError),
        (("execution",), ValueError),
        (("generation",), ValueError),
        (("generation", "execution", "execution"), ValueError),
        (("generation", "execution", "generation"), ValueError),
        (("generation", "execution", "missing"), KeyError),
        (("generation", "execution", "controller"), ValueError),
        (("generation", "execution", "__end__"), ValueError),
        (("generation", "execution", "__start__"), ValueError),
    ],
)
def test_invalid_sequential_topologies(chain, error):
    registry = (
        AgentRegistry().register(MockAuditAgent("generation")).register(MockAuditAgent("execution"))
    )
    with pytest.raises(error):
        WorkflowBuilder(registry, chain)


@pytest.mark.parametrize(
    "name", ["", " ", "controller", "__start__", "__end__", "a:b", "a|b", None, 3]
)
def test_invalid_agent_names(name):
    with pytest.raises(ValueError, match="agent name"):
        AgentRegistry().register(MockAuditAgent(name))
